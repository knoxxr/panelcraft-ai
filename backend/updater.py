"""Auto-update checker and GitHub Issues / Discussions / Releases integration."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from backend.models import UpdateCheckResponse, UpdateConfig
from backend.version import get_app_version, get_runtime_info, is_newer_version


def build_github_links(repo: str, version: str | None = None) -> dict[str, str]:
    clean_repo = repo.strip().strip("/") or "knoxxr/panelcraft-ai"
    ver = version or get_app_version()
    rt = get_runtime_info()
    base = f"https://github.com/{clean_repo}"
    bug_body = urllib.parse.quote(
        f"## Environment\n- PanelCraft AI Version: v{ver}\n- OS: {rt['os']} {rt['os_release']} ({rt['arch']})\n- Python: {rt['python_version']}\n\n## Description\n\n## Steps to Reproduce\n1. \n"
    )
    feat_body = urllib.parse.quote(
        f"## Feature Summary\n\n## Control Panel / Engineering Context\n- Version: v{ver}\n"
    )
    return {
        "repo_url": base,
        "releases_url": f"{base}/releases",
        "issues_url": f"{base}/issues",
        "new_bug_url": f"{base}/issues/new?template=bug_report.yml&labels=bug&body={bug_body}",
        "new_feature_url": f"{base}/issues/new?template=feature_request.yml&labels=enhancement&body={feat_body}",
        "discussions_url": f"{base}/discussions",
        "new_discussion_url": f"{base}/discussions/new/choose",
    }


def _classify_asset_platform(name: str) -> str:
    lower = name.lower()
    if lower.endswith((".exe", ".msi")):
        return "Windows"
    if lower.endswith((".dmg", ".pkg")) or "mac" in lower:
        return "macOS"
    if lower.endswith((".appimage", ".deb", ".rpm")):
        return "Linux"
    if lower.endswith((".apk", ".aab")):
        return "Android"
    return "Other"


def check_github_updates(cfg: UpdateConfig) -> UpdateCheckResponse:
    """Query GitHub Releases API to compare latest release against current VERSION."""
    current = get_app_version()
    clean_repo = cfg.github_repo.strip().strip("/") or "knoxxr/panelcraft-ai"
    checked_at = datetime.now().isoformat(timespec="seconds")
    links = build_github_links(clean_repo, current)

    api_url = (
        f"https://api.github.com/repos/{clean_repo}/releases"
        if cfg.channel == "beta"
        else f"https://api.github.com/repos/{clean_repo}/releases/latest"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"PanelCraft-AI/{current}",
    }

    try:
        req = urllib.request.Request(api_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        release: dict[str, Any] = payload[0] if isinstance(payload, list) and payload else (payload if isinstance(payload, dict) else {})
        latest_tag = str(release.get("tag_name") or current).lstrip("vV")
        update_avail = is_newer_version(latest_tag, current)

        assets = []
        for a in release.get("assets", []):
            assets.append({
                "name": a.get("name", ""),
                "platform": _classify_asset_platform(a.get("name", "")),
                "download_url": a.get("browser_download_url", ""),
                "size_mb": round(float(a.get("size", 0)) / (1024 * 1024), 1),
            })

        return UpdateCheckResponse(
            status="update_available" if update_avail else "up_to_date",
            current_version=current,
            latest_version=latest_tag,
            update_available=update_avail,
            release_url=release.get("html_url") or links["releases_url"],
            release_notes=str(release.get("body") or "")[:1200],
            published_at=str(release.get("published_at") or ""),
            assets=assets,
            checked_at=checked_at,
            message=(
                f"New version v{latest_tag} is available!"
                if update_avail
                else f"You are running the latest version (v{current})."
            ),
        )
    except urllib.error.HTTPError as exc:
        msg = (
            f"GitHub repository '{clean_repo}' has no published releases yet (HTTP {exc.code})."
            if exc.code == 404
            else f"GitHub API returned HTTP {exc.code}."
        )
        return UpdateCheckResponse(
            status="check_failed",
            current_version=current,
            latest_version=current,
            update_available=False,
            release_url=links["releases_url"],
            checked_at=checked_at,
            message=msg,
        )
    except Exception as exc:
        return UpdateCheckResponse(
            status="check_failed",
            current_version=current,
            latest_version=current,
            update_available=False,
            release_url=links["releases_url"],
            checked_at=checked_at,
            message=f"Update check offline/unreachable ({exc.__class__.__name__}). Current version: v{current}.",
        )
