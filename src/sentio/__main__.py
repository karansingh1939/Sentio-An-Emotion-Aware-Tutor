"""Start Sentio with ``python -m sentio`` or the installed ``sentio`` command."""

import argparse

import uvicorn

from sentio.config import api_cfg


def main():
    parser = argparse.ArgumentParser(description="Start the Sentio tutor server.")
    parser.add_argument("--host", default=api_cfg.HOST)
    parser.add_argument("--port", type=int, default=api_cfg.PORT)
    parser.add_argument("--reload", action="store_true", default=api_cfg.RELOAD)
    args = parser.parse_args()
    uvicorn.run("sentio.api.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
