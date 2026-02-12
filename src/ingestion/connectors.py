"""
connectors.py — Data source connectors for code and documentation ingestion.

Supports three input modes:
  1. **Repo URL** — Clone a full GitHub repo and scan it (recommended)
  2. **GitHub API** — Fetch files via GitHub Contents API (slow, needs token)
  3. **Local fallback** — Read from ``data/`` directory (manual file placement)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class RawDocument(BaseModel):
    """A raw document fetched from any data source."""
    content: str
    source: str            # e.g. "github:owner/repo/path" or "local:data/code/Foo.java"
    file_type: str         # e.g. "java", "ts", "md", "html"
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Repo Cloner (NEW — accepts a repo URL)
# ---------------------------------------------------------------------------

# Directories/files to skip when scanning a cloned repo
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "build", "dist", "target", ".gradle", ".mvn", ".idea", ".vscode",
    ".settings", "bin", "obj", ".next", ".nuxt", "coverage",
    ".pytest_cache", ".mypy_cache", ".tox", "vendor",
}

_SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    ".DS_Store", "Thumbs.db",
}


class RepoConnector:
    """
    Clone a Git repository and scan it for code and doc files.

    Usage:
        connector = RepoConnector("https://github.com/owner/repo")
        code_docs, doc_docs = await connector.fetch_all()

    For private repos:
        # Option 1: SSH (uses your machine's SSH keys)
        connector = RepoConnector("git@github.com:owner/private-repo.git")

        # Option 2: GitHub PAT
        connector = RepoConnector(
            "https://github.com/owner/private-repo",
            github_token="ghp_xxxx..."
        )
    """

    def __init__(
        self,
        repo_url: str,
        branch: str = "",
        subdirectory: str = "",
        clone_dir: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> None:
        self.repo_url = repo_url.strip().rstrip("/")
        self.branch = branch
        self.subdirectory = subdirectory
        self._clone_dir = clone_dir  # If None, uses a temp directory
        self._cloned_path: Optional[Path] = None
        self._is_temp = clone_dir is None
        self._github_token = github_token or os.getenv("GITHUB_TOKEN", "")

    @property
    def repo_name(self) -> str:
        """Extract repo name from URL (e.g. 'my-app' from 'https://github.com/org/my-app.git')."""
        name = self.repo_url.split("/")[-1]
        # Handle SSH format: git@github.com:owner/repo.git
        if ":" in name:
            name = name.split(":")[-1].split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name

    def _build_clone_url(self) -> str:
        """
        Build the clone URL, injecting PAT for private HTTPS repos if available.

        - SSH URLs (git@...) → used as-is (relies on SSH keys)
        - HTTPS URLs + PAT → https://<token>@github.com/owner/repo
        - HTTPS URLs without PAT → used as-is (public repos only)
        """
        url = self.repo_url

        # SSH URLs don't need token injection
        if url.startswith("git@") or url.startswith("ssh://"):
            return url

        # Inject PAT into HTTPS URL for private repos
        if self._github_token and "github.com" in url:
            # https://github.com/owner/repo → https://<token>@github.com/owner/repo
            url = url.replace("https://", f"https://{self._github_token}@", 1)

        return url

    def clone(self) -> Path:
        """
        Clone the repository. Returns path to the cloned directory.

        Uses a shallow clone (depth=1) for speed.
        """
        if self._cloned_path and self._cloned_path.exists():
            return self._cloned_path

        if self._clone_dir:
            target = Path(self._clone_dir)
            target.mkdir(parents=True, exist_ok=True)
        else:
            target = Path(tempfile.mkdtemp(prefix="nexus_repo_"))

        clone_url = self._build_clone_url()

        cmd = ["git", "clone", "--depth", "1"]
        if self.branch:
            cmd.extend(["--branch", self.branch])
        cmd.extend([clone_url, str(target / self.repo_name)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            # Sanitize error message to not leak tokens
            error_msg = result.stderr.strip()
            if self._github_token:
                error_msg = error_msg.replace(self._github_token, "***")
            raise RuntimeError(
                f"Failed to clone repo: {error_msg}\n"
                f"URL: {self.repo_url}"
            )

        self._cloned_path = target / self.repo_name

        # If a subdirectory is specified, point to it
        if self.subdirectory:
            subdir = self._cloned_path / self.subdirectory
            if subdir.exists():
                self._cloned_path = subdir

        return self._cloned_path

    def _should_skip(self, path: Path) -> bool:
        """Check if a path should be skipped."""
        for part in path.parts:
            if part in _SKIP_DIRS:
                return True
        if path.name in _SKIP_FILES:
            return True
        return False

    def _scan_files(
        self,
        extensions: set[str],
        root: Path | None = None,
    ) -> list[RawDocument]:
        """Scan the cloned repo for files matching the given extensions."""
        if root is None:
            root = self._cloned_path
        if root is None or not root.exists():
            return []

        documents: list[RawDocument] = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if self._should_skip(file_path):
                continue
            if file_path.suffix not in extensions:
                continue

            # Skip very large files (>500KB likely not useful source)
            try:
                size = file_path.stat().st_size
                if size > 500_000:
                    continue
            except OSError:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                rel_path = file_path.relative_to(self._cloned_path)
                documents.append(RawDocument(
                    content=content,
                    source=f"repo:{self.repo_name}/{rel_path}",
                    file_type=file_path.suffix.lstrip("."),
                    metadata={
                        "local_path": str(file_path),
                        "relative_path": str(rel_path),
                        "repo_url": self.repo_url,
                        "size": size,
                    },
                ))
            except (UnicodeDecodeError, OSError):
                # Skip binary or unreadable files silently
                continue

        return documents

    async def fetch_code(
        self,
        extensions: set[str] | None = None,
    ) -> list[RawDocument]:
        """
        Clone the repo (if not already) and return code files.

        Args:
            extensions: Code file extensions to include.
                        Defaults to Java, TypeScript, JavaScript, Python.
        """
        if extensions is None:
            extensions = {".java", ".ts", ".tsx", ".py", ".js", ".jsx", ".kt", ".go", ".rs"}

        self.clone()
        return self._scan_files(extensions)

    async def fetch_docs(
        self,
        extensions: set[str] | None = None,
    ) -> list[RawDocument]:
        """
        Clone the repo (if not already) and return documentation files.

        Args:
            extensions: Doc file extensions to include.
                        Defaults to Markdown, HTML, RST, TXT.
        """
        if extensions is None:
            extensions = {".md", ".html", ".txt", ".rst", ".adoc"}

        self.clone()
        return self._scan_files(extensions)

    async def fetch_all(
        self,
        code_extensions: set[str] | None = None,
        doc_extensions: set[str] | None = None,
    ) -> tuple[list[RawDocument], list[RawDocument]]:
        """
        Clone and return both code and doc files in one call.

        Returns:
            Tuple of (code_documents, doc_documents).
        """
        self.clone()
        code_docs = await self.fetch_code(code_extensions)
        doc_docs = await self.fetch_docs(doc_extensions)
        return code_docs, doc_docs

    def get_stats(self) -> dict:
        """Return stats about the cloned repo."""
        if not self._cloned_path or not self._cloned_path.exists():
            return {"cloned": False}

        all_files = [f for f in self._cloned_path.rglob("*") if f.is_file() and not self._should_skip(f)]
        by_ext: dict[str, int] = {}
        for f in all_files:
            by_ext[f.suffix] = by_ext.get(f.suffix, 0) + 1

        return {
            "cloned": True,
            "repo_url": self.repo_url,
            "repo_name": self.repo_name,
            "total_files": len(all_files),
            "files_by_extension": dict(sorted(by_ext.items(), key=lambda x: -x[1])),
        }

    def cleanup(self) -> None:
        """Remove the cloned repository from disk."""
        if self._is_temp and self._cloned_path and self._cloned_path.exists():
            shutil.rmtree(self._cloned_path.parent, ignore_errors=True)
            self._cloned_path = None


# ---------------------------------------------------------------------------
# Multi-Repo Connector (combines multiple repos into one skill)
# ---------------------------------------------------------------------------

class MultiRepoConnector:
    """
    Clone and scan multiple Git repositories, merging results for a single skill.

    Usage:
        connector = MultiRepoConnector([
            {"url": "https://github.com/org/backend", "branch": "main"},
            {"url": "https://github.com/org/frontend", "subdirectory": "src"},
            {"url": "git@github.com:org/shared-lib.git"},
        ])
        code_docs, doc_docs, stats = await connector.fetch_all()
        connector.cleanup()
    """

    def __init__(
        self,
        repos: list[dict],
        github_token: Optional[str] = None,
    ) -> None:
        """
        Args:
            repos: List of repo configs. Each dict can have:
                   - url (required): Git clone URL
                   - branch (optional): Branch to clone
                   - subdirectory (optional): Subdirectory to focus on
            github_token: GitHub PAT for private repos (applies to all HTTPS repos).
        """
        self._token = github_token or os.getenv("GITHUB_TOKEN", "")
        self._connectors: list[RepoConnector] = []

        for repo_config in repos:
            url = repo_config.get("url", "").strip()
            if not url:
                continue
            self._connectors.append(RepoConnector(
                repo_url=url,
                branch=repo_config.get("branch", ""),
                subdirectory=repo_config.get("subdirectory", ""),
                github_token=self._token,
            ))

    @property
    def repo_count(self) -> int:
        return len(self._connectors)

    def clone_all(self) -> list[dict]:
        """
        Clone all repositories. Returns a list of per-repo results.

        Each result is a dict with:
            - repo_url: The repo URL
            - repo_name: The extracted repo name
            - success: Whether the clone succeeded
            - error: Error message (if failed)
            - stats: Repo stats (if succeeded)
        """
        results = []
        for connector in self._connectors:
            try:
                connector.clone()
                results.append({
                    "repo_url": connector.repo_url,
                    "repo_name": connector.repo_name,
                    "success": True,
                    "error": None,
                    "stats": connector.get_stats(),
                })
            except RuntimeError as e:
                results.append({
                    "repo_url": connector.repo_url,
                    "repo_name": connector.repo_name,
                    "success": False,
                    "error": str(e),
                    "stats": None,
                })
        return results

    async def fetch_all(
        self,
        code_extensions: set[str] | None = None,
        doc_extensions: set[str] | None = None,
    ) -> tuple[list[RawDocument], list[RawDocument], list[dict]]:
        """
        Clone all repos and merge their code + doc files.

        Returns:
            Tuple of (all_code_docs, all_doc_docs, per_repo_stats).
        """
        clone_results = self.clone_all()

        all_code: list[RawDocument] = []
        all_docs: list[RawDocument] = []

        for connector, result in zip(self._connectors, clone_results):
            if not result["success"]:
                continue  # Skip repos that failed to clone
            code = await connector.fetch_code(code_extensions)
            docs = await connector.fetch_docs(doc_extensions)
            all_code.extend(code)
            all_docs.extend(docs)

        return all_code, all_docs, clone_results

    def get_combined_stats(self) -> dict:
        """Return combined stats across all repos."""
        total_files = 0
        repos_cloned = 0
        by_ext: dict[str, int] = {}

        for connector in self._connectors:
            stats = connector.get_stats()
            if stats.get("cloned"):
                repos_cloned += 1
                total_files += stats.get("total_files", 0)
                for ext, count in stats.get("files_by_extension", {}).items():
                    by_ext[ext] = by_ext.get(ext, 0) + count

        return {
            "repos_total": len(self._connectors),
            "repos_cloned": repos_cloned,
            "total_files": total_files,
            "files_by_extension": dict(sorted(by_ext.items(), key=lambda x: -x[1])),
        }

    def cleanup(self) -> None:
        """Remove all cloned repositories from disk."""
        for connector in self._connectors:
            connector.cleanup()


# ---------------------------------------------------------------------------
# GitHub Connector (API mode + local fallback)
# ---------------------------------------------------------------------------

class GitHubConnector:
    """
    Fetches source code files from a GitHub repository.
    Falls back to reading from ``data/code/`` if GITHUB_TOKEN is not set.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        local_dir: str = "data/code",
    ) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.repo = repo or os.getenv("GITHUB_REPO", "")
        self.local_dir = Path(local_dir)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_live(self) -> bool:
        return bool(self.token and self.repo)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=30.0,
            )
        return self._client

    async def fetch_files(
        self,
        path: str = "",
        extensions: set[str] | None = None,
    ) -> list[RawDocument]:
        """
        Fetch code files, either from GitHub API or local fallback.

        Args:
            path:       Subdirectory within the repo to scan.
            extensions: File extensions to include (e.g. {".java", ".ts"}).
                        If None, includes all supported code extensions.
        """
        if extensions is None:
            extensions = {".java", ".ts", ".tsx", ".py", ".js", ".jsx"}

        if self.is_live:
            return await self._fetch_from_github(path, extensions)
        return self._fetch_from_local(extensions)

    async def _fetch_from_github(
        self,
        path: str,
        extensions: set[str],
    ) -> list[RawDocument]:
        """Recursively fetch files from GitHub Contents API."""
        client = await self._get_client()
        url = f"/repos/{self.repo}/contents/{path}"
        response = await client.get(url)
        response.raise_for_status()

        items = response.json()
        if not isinstance(items, list):
            items = [items]

        documents: list[RawDocument] = []

        for item in items:
            if item["type"] == "dir":
                sub_docs = await self._fetch_from_github(item["path"], extensions)
                documents.extend(sub_docs)
            elif item["type"] == "file":
                file_ext = "." + item["name"].rsplit(".", 1)[-1] if "." in item["name"] else ""
                if file_ext in extensions:
                    # Fetch file content
                    file_resp = await client.get(item["download_url"])
                    file_resp.raise_for_status()
                    documents.append(RawDocument(
                        content=file_resp.text,
                        source=f"github:{self.repo}/{item['path']}",
                        file_type=file_ext.lstrip("."),
                        metadata={
                            "sha": item.get("sha", ""),
                            "size": item.get("size", 0),
                            "url": item.get("html_url", ""),
                        },
                    ))

        return documents

    def _fetch_from_local(self, extensions: set[str]) -> list[RawDocument]:
        """Read code files from the local data/ directory."""
        documents: list[RawDocument] = []

        if not self.local_dir.exists():
            return documents

        for file_path in self.local_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    documents.append(RawDocument(
                        content=content,
                        source=f"local:{file_path}",
                        file_type=file_path.suffix.lstrip("."),
                        metadata={"local_path": str(file_path)},
                    ))
                except (UnicodeDecodeError, OSError) as e:
                    print(f"⚠️  Skipping {file_path}: {e}")

        return documents

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ---------------------------------------------------------------------------
# Confluence Connector
# ---------------------------------------------------------------------------

class ConfluenceConnector:
    """
    Fetches documentation pages from Confluence.
    Falls back to reading from ``data/docs/`` if credentials are not set.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        space_key: Optional[str] = None,
        local_dir: str = "data/docs",
    ) -> None:
        self.url = (url or os.getenv("CONFLUENCE_URL", "")).rstrip("/")
        self.token = token or os.getenv("CONFLUENCE_TOKEN", "")
        self.space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY", "")
        self.local_dir = Path(local_dir)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_live(self) -> bool:
        return bool(self.url and self.token)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def fetch_pages(self) -> list[RawDocument]:
        """
        Fetch documentation pages from Confluence API or local fallback.
        """
        if self.is_live:
            return await self._fetch_from_confluence()
        return self._fetch_from_local()

    async def _fetch_from_confluence(self) -> list[RawDocument]:
        """Fetch pages from Confluence REST API v2."""
        client = await self._get_client()
        documents: list[RawDocument] = []

        # Paginate through space content
        url = "/wiki/api/v2/spaces"
        params = {"keys": self.space_key, "limit": 25}

        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        for space in data.get("results", []):
            space_id = space["id"]
            pages_url = f"/wiki/api/v2/spaces/{space_id}/pages"
            pages_resp = await client.get(pages_url, params={"limit": 100})
            pages_resp.raise_for_status()

            for page in pages_resp.json().get("results", []):
                # Fetch page body
                body_url = f"/wiki/api/v2/pages/{page['id']}?body-format=storage"
                body_resp = await client.get(body_url)
                body_resp.raise_for_status()
                body_data = body_resp.json()

                content = body_data.get("body", {}).get("storage", {}).get("value", "")
                documents.append(RawDocument(
                    content=content,
                    source=f"confluence:{self.space_key}/{page['title']}",
                    file_type="html",
                    metadata={
                        "page_id": page["id"],
                        "title": page["title"],
                        "space": self.space_key,
                    },
                ))

        return documents

    def _fetch_from_local(self) -> list[RawDocument]:
        """Read documentation files from the local data/docs/ directory."""
        documents: list[RawDocument] = []
        doc_extensions = {".md", ".html", ".txt", ".rst"}

        if not self.local_dir.exists():
            return documents

        for file_path in self.local_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in doc_extensions:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    documents.append(RawDocument(
                        content=content,
                        source=f"local:{file_path}",
                        file_type=file_path.suffix.lstrip("."),
                        metadata={
                            "local_path": str(file_path),
                            "title": file_path.stem,
                        },
                    ))
                except (UnicodeDecodeError, OSError) as e:
                    print(f"⚠️  Skipping {file_path}: {e}")

        return documents

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
