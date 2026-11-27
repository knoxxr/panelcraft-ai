"""Application version management and semantic version comparison utilities."""

from __future__ import annotations

import platform
import re
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT_DIR / "VERSION"
CHANGELOG_FILE = ROOT_DIR / "CHANGELOG.md"


def get_app_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.3.0"


def parse_semver(version_str: str) -> tuple[int, int, int]:
    cleaned = version_str.strip().lstrip("vV")
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", cleaned)
    if not m:
        return (0, 0, 0)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def is_newer_version(latest: str, current: str) -> bool:
    return parse_semver(latest) > parse_semver(current)


def read_changelog_entries() -> list[dict[str, Any]]:
    if not CHANGELOG_FILE.exists():
        return []
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in text.splitlines():
        m = re.match(r"^##\s+\[([^\]]+)\]\s*-\s*(.+)$", line.strip())
        if m:
            if cur:
                entries.append(cur)
            cur = {"version": m.group(1).strip(), "date": m.group(2).strip(), "items": []}
        elif cur and line.strip().startswith("- "):
            cur["items"].append(line.strip()[2:])
    if cur:
        entries.append(cur)
    return entries


def get_runtime_info() -> dict[str, str]:
    return {
        "app_version": get_app_version(),
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
