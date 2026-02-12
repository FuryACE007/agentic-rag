"""
registry.py — Skill manifest manager for Nexus.

Scans the manifests directory for *_SKILLS.md files, provides loading,
saving, and listing functionality.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class SkillRegistry:
    """
    Manages skill manifest files (SKILLS.md) stored in the manifests directory.

    Each skill is stored as ``{SKILL_NAME}_SKILLS.md`` in the configured
    manifests directory.
    """

    def __init__(self, manifests_dir: Optional[str] = None) -> None:
        self.manifests_dir = Path(
            manifests_dir or os.getenv("SKILLS_MANIFEST_DIR", "./src/skills/manifests")
        )
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[str]:
        """
        List all available skill names by scanning the manifests directory.

        Returns:
            Sorted list of skill names (e.g. ["authentication", "staking"]).
        """
        skills: list[str] = []
        for file_path in self.manifests_dir.glob("*_SKILLS.md"):
            # Extract skill name from filename: STAKING_SKILLS.md -> staking
            name = file_path.stem.replace("_SKILLS", "").lower()
            if name:
                skills.append(name)
        return sorted(skills)

    def load_skill(self, skill_name: str) -> str:
        """
        Load the content of a skill's SKILLS.md manifest.

        Args:
            skill_name: The skill name (case-insensitive).

        Returns:
            The Markdown content, or an empty string if not found.
        """
        file_path = self._skill_path(skill_name)
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return ""

    def save_skill(self, skill_name: str, content: str) -> Path:
        """
        Save a generated SKILLS.md manifest.

        Args:
            skill_name: The skill name (will be uppercased in filename).
            content:    The Markdown content to write.

        Returns:
            Path to the saved file.
        """
        file_path = self._skill_path(skill_name)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def delete_skill(self, skill_name: str) -> bool:
        """
        Delete a skill manifest.

        Returns:
            True if the file was deleted, False if it didn't exist.
        """
        file_path = self._skill_path(skill_name)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def skill_exists(self, skill_name: str) -> bool:
        """Check whether a manifest exists for the given skill."""
        return self._skill_path(skill_name).exists()

    def _skill_path(self, skill_name: str) -> Path:
        """Build the file path for a skill manifest."""
        normalized = re.sub(r"[^a-zA-Z0-9_]", "_", skill_name.strip()).upper()
        return self.manifests_dir / f"{normalized}_SKILLS.md"
