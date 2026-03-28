"""OAuth configuration loader from environment variables."""

import os
from dataclasses import dataclass
from urllib.parse import urljoin

from dotenv import load_dotenv


@dataclass
class OAuthConfig:
    """OAuth configuration."""

    provider_url: str
    """The OAuth provider's authorization endpoint URL."""

    token_endpoint: str
    """The OAuth provider's token endpoint URL."""

    client_id: str
    """OAuth client ID."""

    client_secret: str
    """OAuth client secret."""

    redirect_path: str = "/auth/callback"
    """Path for OAuth callback (relative to app)."""

    scopes: str = "openid email profile"
    """OAuth scopes to request."""

    @property
    def redirect_uri_template(self) -> str:
        """Template for redirect URI; {host} and {port} are replaced at runtime."""
        base = "http://{host}:{port}"
        return urljoin(f"{base}/", self.redirect_path.lstrip("/"))


def load_oauth_config() -> OAuthConfig:
    """Load OAuth config from environment variables.

    Requires:
    - OAUTH_PROVIDER_URL: Authorization endpoint
    - OAUTH_TOKEN_ENDPOINT: Token exchange endpoint
    - OAUTH_CLIENT_ID: Client ID
    - OAUTH_CLIENT_SECRET: Client secret

    Optional:
    - OAUTH_REDIRECT_PATH: Callback path (default: /auth/callback)
    - OAUTH_SCOPES: Space-separated scopes (default: openid email profile)

    Raises:
        ValueError: If required env vars are missing.
    """
    load_dotenv()

    provider_url = os.getenv("OAUTH_PROVIDER_URL")
    token_endpoint = os.getenv("OAUTH_TOKEN_ENDPOINT")
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")

    if not all([provider_url, token_endpoint, client_id, client_secret]):
        missing = [
            key
            for key, val in {
                "OAUTH_PROVIDER_URL": provider_url,
                "OAUTH_TOKEN_ENDPOINT": token_endpoint,
                "OAUTH_CLIENT_ID": client_id,
                "OAUTH_CLIENT_SECRET": client_secret,
            }.items()
            if not val
        ]
        raise ValueError(f"Missing required OAuth env vars: {', '.join(missing)}")

    return OAuthConfig(
        provider_url=provider_url,
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=client_secret,
        redirect_path=os.getenv("OAUTH_REDIRECT_PATH", "/auth/callback"),
        scopes=os.getenv("OAUTH_SCOPES", "openid email profile"),
    )
