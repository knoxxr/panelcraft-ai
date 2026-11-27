"""Standalone entrypoint for PyInstaller-bundled PanelCraft AI backend binary."""

from __future__ import annotations

import argparse
import uvicorn

from backend.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="PanelCraft AI Embedded Backend Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
