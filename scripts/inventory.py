#!/usr/bin/env python3
"""Inventory vendored prediction-market projects without executing them."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor"
MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "docker-compose.yml",
    "Dockerfile",
    "LICENSE",
    "LICENSE.md",
    "README.md",
}
EXCLUDED_PARTS = {
    ".git", ".venv", ".pytest_cache", "node_modules", "__pycache__", "dist", "build"
}


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return completed.stdout.strip()


def inventory(repo: Path) -> dict[str, object]:
    manifests = sorted(
        str(path.relative_to(repo)).replace("\\", "/")
        for path in repo.rglob("*")
        if path.is_file()
        and path.name in MANIFESTS
        and not EXCLUDED_PARTS.intersection(path.relative_to(repo).parts)
    )
    return {
        "name": repo.name,
        "commit": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "branch", "--show-current"),
        "dirty": bool(git(repo, "status", "--short")),
        "manifests": manifests,
    }


def main() -> None:
    repos = sorted(path for path in VENDOR.iterdir() if (path / ".git").is_dir())
    result = {"vendor_root": str(VENDOR), "repositories": [inventory(r) for r in repos]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
