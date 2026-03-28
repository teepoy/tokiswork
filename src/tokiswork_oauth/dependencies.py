"""FastAPI dependencies for OAuth authentication."""

from starlette.requests import Request


def get_user(request: Request) -> str | None:
    """FastAPI dependency to extract authenticated user from session.

    Returns:
        Username if user is authenticated in session, else None.
        Returning None will trigger Gradio's login flow.
    """
    user_info = request.session.get("user")
    if user_info:
        return user_info.get("username")
    return None
