"""
connectors.py — Data source connectors for code and documentation ingestion.

Provides GitHubConnector and ConfluenceConnector classes that can either
pull from live APIs (when tokens are configured) or fall back to reading
from the local ``data/`` directory for MVP development.
"""

from __future__ import annotations

import os
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
# GitHub Connector
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
