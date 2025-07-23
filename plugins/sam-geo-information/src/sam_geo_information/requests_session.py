import requests


class RequestsSessionManager:
    """A singleton manager for a shared requests.Session object."""

    _instance = None
    _session = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RequestsSessionManager, cls).__new__(cls)
            cls._session = requests.Session()
        return cls._instance

    def get_session(self) -> requests.Session:
        """Returns the shared requests.Session object."""
        return self._session


requests_session_manager = RequestsSessionManager()
