"""FastAPI OAuth wrapper for Gradio applications."""

import logging
import secrets
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from tokiswork_dspy.gradio_app import build_demo
from .config import OAuthConfig
from .dependencies import get_user

logger = logging.getLogger(__name__)


def create_app(config: OAuthConfig, session_secret: str | None = None) -> FastAPI:
    """Create FastAPI app with OAuth flow and Gradio mounting.

    Args:
        config: OAuth configuration.
        session_secret: Secret key for session middleware. If None, a random one is generated
                       (NOTE: this means sessions won't persist across app restarts).

    Returns:
        FastAPI app ready to launch.
    """
    if session_secret is None:
        session_secret = secrets.token_urlsafe(32)
        logger.warning(
            "No session secret provided; generating random one. "
            "Sessions will NOT persist across app restarts. "
            "Set SESSION_SECRET env var for persistence."
        )

    app = FastAPI(title="tokiswork OAuth + Gradio")

    # Add session middleware first (must be before routes)
    app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=86400)

    # Store config in app state for use in route handlers
    app.state.oauth_config = config

    @app.get("/")
    async def index():
        """Redirect to Gradio app."""
        return RedirectResponse(url="/gradio")

    @app.get("/login")
    async def login(request: Request):
        """Initiate OAuth flow.

        1. Generate a state token for CSRF protection
        2. Store it in session
        3. Redirect to OAuth provider
        """
        state = secrets.token_urlsafe(32)
        request.session["oauth_state"] = state

        # Build redirect to OAuth provider
        redirect_uri = config.redirect_uri_template.format(
            host=request.client.host,
            port=request.url.port or 80,
        )

        # Construct authorization URL
        auth_url = (
            f"{config.provider_url}?"
            f"client_id={config.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}&"
            f"response_type=code&"
            f"scope={config.scopes}"
        )

        logger.info(f"Initiating OAuth flow for {request.client.host}")
        return RedirectResponse(url=auth_url)

    @app.get("/auth/callback")
    async def auth_callback(
        request: Request, code: str | None = None, state: str | None = None
    ):
        """Handle OAuth callback.

        1. Validate state token (CSRF check)
        2. Exchange code for token
        3. Retrieve user info
        4. Store in session
        5. Redirect to Gradio app
        """
        # Validate state token
        stored_state = request.session.get("oauth_state")
        if not stored_state or stored_state != state:
            logger.warning(
                f"State token mismatch from {request.client.host}. Possible CSRF attack."
            )
            return _error_response("Invalid state token. Authentication failed.", 400)

        if not code:
            logger.warning(f"Missing authorization code from {request.client.host}")
            return _error_response("Missing authorization code.", 400)

        # Exchange code for token
        redirect_uri = config.redirect_uri_template.format(
            host=request.client.host,
            port=request.url.port or 80,
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.token_endpoint,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": config.client_id,
                        "client_secret": config.client_secret,
                    },
                )
                response.raise_for_status()
                token_data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed: {e}")
            return _error_response(
                f"Failed to exchange authorization code. {str(e)[:100]}",
                500,
            )

        # Extract user info from token response
        # NOTE: Adjust based on your OAuth provider's response format
        # Common fields: 'id_token' (JWT), 'access_token'
        access_token = token_data.get("access_token")

        # For now, store basic info; extend based on provider's user info endpoint
        user_info = {
            "username": token_data.get("username") or f"user_{secrets.token_hex(4)}",
            "access_token": access_token,
        }

        request.session["user"] = user_info
        logger.info(
            f"User {user_info['username']} authenticated from {request.client.host}"
        )

        return RedirectResponse(url="/gradio")

    @app.get("/logout")
    async def logout(request: Request):
        """Clear session and redirect to login."""
        username = request.session.get("user", {}).get("username", "unknown")
        request.session.clear()
        logger.info(f"User {username} logged out from {request.client.host}")
        return RedirectResponse(url="/login")

    # Mount Gradio app
    try:
        import gradio as gr

        demo = build_demo()
        app = gr.mount_gradio_app(
            app,
            demo,
            path="/gradio",
            auth_dependency=get_user,
        )
        logger.info("Gradio app mounted at /gradio")
    except Exception as e:
        logger.error(f"Failed to mount Gradio app: {e}")
        raise

    return app


def _error_response(message: str, status_code: int = 400) -> dict[str, Any]:
    """Return an error response as HTML."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authentication Error</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .error {{ color: #d32f2f; }}
            a {{ color: #1976d2; }}
        </style>
    </head>
    <body>
        <h1 class="error">Authentication Error</h1>
        <p>{message}</p>
        <p><a href="/login">Try again</a></p>
    </body>
    </html>
    """
    return {
        "content": html,
        "status_code": status_code,
        "headers": {"content-type": "text/html"},
    }
