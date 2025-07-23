"""
Manages web user sessions and mapping to A2A Client IDs.
"""

import uuid
from starlette.requests import Request
from typing import Optional, Callable, Dict, Any

from solace_ai_connector.common.log import log

SESSION_KEY_CLIENT_ID = "a2a_client_id"
SESSION_KEY_SESSION_ID = "a2a_session_id"
SESSION_KEY_ACCESS_TOKEN = "access_token"
SESSION_KEY_REFRESH_TOKEN = "refresh_token"
SESSION_KEY_USER_ID = "user_id"


class SessionManager:
    """
    Handles web user sessions using Starlette's SessionMiddleware.
    Generates and stores unique A2A Client IDs and manages the current A2A Session ID per web session.
    """

    def __init__(self, secret_key: str, app_config: Dict[str, Any]):
        if not secret_key:
            raise ValueError("Session secret key cannot be empty.")
        self.secret_key = secret_key
        self.force_user_identity = app_config.get("force_user_identity")
        self.default_user_identity = app_config.get("default_user_identity")
        self._temp_code_cache = {}
        log.info("[SessionManager] Initialized.")
        if self.force_user_identity:
            log.warning(
                f"[SessionManager] Forcing user identity to: {self.force_user_identity}"
            )

    def _get_or_create_client_id(self, request: Request) -> str:
        """
        Retrieves the A2A Client ID. It prioritizes the authenticated user from
        `request.state.user` and falls back to session-based or generated IDs.
        """
        if self.force_user_identity:
            return self.force_user_identity

        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.get("id")
            if user_id:
                log.debug(
                    "[SessionManager] Using authenticated user ID from request.state: %s",
                    user_id,
                )
                return user_id
            else:
                log.warning(
                    "[SessionManager] request.state.user exists but has no 'id' field. Falling back to other methods."
                )

        user_id = self.get_user_id(request)
        if user_id:
            log.debug(
                "[SessionManager] Using authenticated user_id from session as A2A Client ID: %s",
                user_id,
            )
            return user_id

        client_id = request.session.get(SESSION_KEY_CLIENT_ID)
        if not client_id:
            if self.default_user_identity:
                log.info(
                    "[SessionManager] Using default_user_identity as A2A Client ID: %s",
                    self.default_user_identity,
                )
                client_id = self.default_user_identity
            else:
                client_id = f"web-client-{uuid.uuid4().hex}"
                log.info(
                    "[SessionManager] Created new A2A Client ID: %s for web session.",
                    client_id,
                )
            request.session[SESSION_KEY_CLIENT_ID] = client_id
        else:
            log.debug(
                "[SessionManager] Using existing A2A Client ID: %s for web session.",
                client_id,
            )
        return client_id

    def get_a2a_client_id(self, request: Request) -> str:
        """
        FastAPI dependency callable to get the A2A Client ID for the current request.
        Ensures a client ID exists in the session.
        """
        return self._get_or_create_client_id(request)

    def get_a2a_session_id(self, request: Request) -> Optional[str]:
        """
        FastAPI dependency callable to get the current A2A Session ID for the current request.
        Returns None if no session has been started for the current agent in this web session.
        """
        session_id = request.session.get(SESSION_KEY_SESSION_ID)
        log.debug("[SessionManager] Retrieving A2A Session ID: %s", session_id)
        return session_id

    def start_new_a2a_session(self, request: Request) -> str:
        """
        Generates a new A2A Session ID, stores it in the web session, and returns it.
        This should be called when the user explicitly starts a new chat or switches agents.
        """
        client_id = self._get_or_create_client_id(request)
        new_session_id = f"web-session-{uuid.uuid4().hex}"
        request.session[SESSION_KEY_SESSION_ID] = new_session_id
        log.info(
            "[SessionManager] Started new A2A Session ID: %s for Client ID: %s",
            new_session_id,
            client_id,
        )
        return new_session_id

    def ensure_a2a_session(self, request: Request) -> str:
        """
        Ensures an A2A session ID exists, creating one if necessary.
        Use this when an operation requires a session ID but one might not have been explicitly started yet.
        """
        session_id = self.get_a2a_session_id(request)
        if not session_id:
            session_id = self.start_new_a2a_session(request)
            log.info(
                "[SessionManager] No A2A Session ID found, created new one via ensure_a2a_session: %s",
                session_id,
            )
        return session_id

    def store_auth_tokens(
        self, request: Request, access_token: str, refresh_token: Optional[str] = None
    ):
        """
        Stores authentication tokens directly in the user's session.
        """
        request.session[SESSION_KEY_ACCESS_TOKEN] = access_token
        if refresh_token:
            request.session[SESSION_KEY_REFRESH_TOKEN] = refresh_token
        log.info("[SessionManager] Stored auth tokens directly in session.")

    def get_access_token(self, request: Request) -> Optional[str]:
        """
        Retrieves the access token from the web session.
        """
        return request.session.get(SESSION_KEY_ACCESS_TOKEN)

    def get_refresh_token(self, request: Request) -> Optional[str]:
        """
        Retrieves the refresh token from the web session.
        """
        return request.session.get(SESSION_KEY_REFRESH_TOKEN)

    def clear_auth_tokens(self, request: Request) -> None:
        """
        Clears authentication tokens from the web session.
        """
        request.session.pop(SESSION_KEY_ACCESS_TOKEN, None)
        request.session.pop(SESSION_KEY_REFRESH_TOKEN, None)
        log.info("[SessionManager] Cleared auth tokens from session")

    def store_user_id(self, request: Request, user_id: str) -> None:
        """
        Stores the user ID in the web session.
        """
        request.session[SESSION_KEY_USER_ID] = user_id
        log.info("[SessionManager] Stored user ID in session: %s", user_id)

    def get_user_id(self, request: Request) -> Optional[str]:
        """
        Retrieves the user ID from the web session.
        """
        return request.session.get(SESSION_KEY_USER_ID)

    def dep_get_client_id(self) -> Callable[[Request], str]:
        """Returns a callable suitable for FastAPI Depends to get the client ID."""
        return self.get_a2a_client_id

    def dep_get_session_id(self) -> Callable[[Request], Optional[str]]:
        """Returns a callable suitable for FastAPI Depends to get the current session ID."""
        return self.get_a2a_session_id

    def dep_ensure_session_id(self) -> Callable[[Request], str]:
        """Returns a callable suitable for FastAPI Depends to ensure a session ID exists."""
        return self.ensure_a2a_session
