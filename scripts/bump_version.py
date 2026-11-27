#!/usr/bin/env python3
"""Bump PanelCraft AI semantic version consistently across VERSION, desktop, mobile, and PWA files.

Usage:
    python3 scripts/bump_version.py 0.4.0
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2 or not re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$", sys.argv[1]):
        print("Usage: python3 scripts/bump_version.py <semver>  (e.g., 0.4.0)")
        sys.exit(1)

    new_ver = sys.argv[1]
    (ROOT / "VERSION").write_text(new_ver + "\n", encoding="utf-8")

    for pkg_rel in ("desktop/package.json", "mobile/package.json"):
        pkg_path = ROOT / pkg_rel
        if pkg_path.exists():
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            data["version"] = new_ver
            pkg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sw_path = ROOT / "frontend/sw.js"
    if sw_path.exists():
        text = sw_path.read_text(encoding="utf-8")
        text = re.sub(r'panelcraft-ai-v[0-9A-Za-z.\-]+', f"panelcraft-ai-v{new_ver}", text)
        sw_path.write_text(text, encoding="utf-8")

    print(f"Updated PanelCraft AI version to v{new_ver} across VERSION, desktop, mobile, and sw.js.")


if __name__ == "__main__":
    main()
