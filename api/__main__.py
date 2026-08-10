"""`python -m api` — start the SafeVision AI server.

Defaults come from .env (API_HOST / API_PORT / API_RELOAD); command-line flags
override them for a one-off run.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

import config as cfg  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="SafeVision AI API server")
    parser.add_argument("--host", default=cfg.API_HOST, help=f"default: {cfg.API_HOST}")
    parser.add_argument("--port", type=int, default=cfg.API_PORT, help=f"default: {cfg.API_PORT}")
    parser.add_argument(
        "--reload",
        action="store_true",
        default=cfg.API_RELOAD,
        help="Reload on code changes",
    )
    args = parser.parse_args()

    display_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    print(f"\n  SafeVision AI  ->  http://{display_host}:{args.port}")
    print(f"  API docs       ->  http://{display_host}:{args.port}/docs\n")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
