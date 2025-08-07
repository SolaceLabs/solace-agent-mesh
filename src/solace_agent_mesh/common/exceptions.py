"""Custom exceptions for Solace Agent Mesh."""


class MessageSizeExceededError(Exception):
    """Raised when a message exceeds the maximum allowed size."""

    def __init__(self, actual_size: int, max_size: int, message: str = None):
        """Initialize the MessageSizeExceededError.

        Args:
            actual_size: The actual size of the message in bytes.
            max_size: The maximum allowed size in bytes.
            message: Optional custom error message. If None, a default message
                    will be generated.
        """
        self.actual_size = actual_size
        self.max_size = max_size

        if message is None:
            message = (
                f"Message size {actual_size} bytes exceeds maximum limit of "
                f"{max_size} bytes"
            )

        super().__init__(message)
