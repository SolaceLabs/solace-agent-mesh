"""
Centralized custom exceptions for the evaluation module.
"""

class EvaluationError(Exception):
    """Base exception for all evaluation-related errors."""
    pass

# Test Case Errors
class TestCaseError(EvaluationError):
    """Base exception for test case-related errors."""
    pass

class TestCaseFileNotFoundError(TestCaseError):
    """Raised when the test case file is not found."""
    pass

class TestCaseParseError(TestCaseError):
    """Raised when the test case file cannot be parsed or validated."""
    pass

# Subscriber Errors
class SubscriberError(EvaluationError):
    """Base exception for subscriber-related errors."""
    pass

class BrokerConnectionError(SubscriberError):
    """Raised when broker connection fails."""
    pass

class MessageProcessingError(SubscriberError):
    """Raised when message processing fails."""
    pass

class ConfigurationError(SubscriberError):
    """Raised when configuration is invalid."""
    pass

# Message Organizer Errors
class CategorizationError(EvaluationError):
    """Base exception for categorization errors."""
    pass

class MissingFileError(CategorizationError):
    """Raised when required files are missing."""
    pass

class InvalidDataError(CategorizationError):
    """Raised when data format is invalid."""
    pass
