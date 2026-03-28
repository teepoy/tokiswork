"""CLI launcher for OAuth-protected Gradio app."""

import argparse
import logging
import os
import sys

from .app import create_app
from .config import load_oauth_config

logger = logging.getLogger(__name__)


def launch_oauth_cli(argv: list[str] | None = None) -> int:
    """Launch FastAPI app with OAuth and Gradio.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        description="Launch tokiswork Gradio with custom OAuth authentication"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        help="Host for server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("GRADIO_SERVER_PORT", 7860)),
        help="Port for server (default: 7860)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (dev mode)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
        help="Logging level (default: info)",
    )

    args = parser.parse_args(argv)

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        # Load OAuth config (will raise if missing required env vars)
        config = load_oauth_config()
        logger.info(
            f"OAuth config loaded: provider={config.provider_url}, "
            f"redirect_path={config.redirect_path}"
        )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        print("\nPlease set required environment variables:", file=sys.stderr)
        print("  - OAUTH_PROVIDER_URL", file=sys.stderr)
        print("  - OAUTH_TOKEN_ENDPOINT", file=sys.stderr)
        print("  - OAUTH_CLIENT_ID", file=sys.stderr)
        print("  - OAUTH_CLIENT_SECRET", file=sys.stderr)
        print("\nSee .env.example for configuration template.", file=sys.stderr)
        return 1

    # Create app
    app = create_app(config, session_secret=os.getenv("SESSION_SECRET"))

    # Launch via uvicorn
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn not installed. Install with: pip install uvicorn")
        return 1

    logger.info(f"Starting server at http://{args.host}:{args.port}")
    logger.info("Open http://{args.host}:{args.port}/gradio in your browser")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(launch_oauth_cli())
