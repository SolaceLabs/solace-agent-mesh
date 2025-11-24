"""
Centralized colored logging configuration for Solace Agent Mesh.

This module provides colored console logging to make it easier to identify
errors, warnings, and different log levels in the terminal output.
"""

import logging
import sys
from typing import Optional


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright foreground colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to log levels and component names.
    
    Color scheme:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bold Red
    - Backend logs (containing 'gateway', 'http_sse', 'fastapi', 'uvicorn'): Blue
    """
    
    # Log level colors
    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.RED,
    }
    
    # Keywords that identify backend logs
    BACKEND_KEYWORDS = ['gateway', 'http_sse', 'fastapi', 'uvicorn', 'starlette']
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, use_colors: bool = True):
        """
        Initialize the colored formatter.
        
        Args:
            fmt: Log format string
            datefmt: Date format string
            use_colors: Whether to use colors (can be disabled for non-TTY outputs)
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()
    
    @staticmethod
    def _supports_color() -> bool:
        """
        Check if the terminal supports color output.
        
        Returns:
            True if colors are supported, False otherwise
        """
        # Check if stdout is a TTY
        if not hasattr(sys.stdout, 'isatty'):
            return False
        if not sys.stdout.isatty():
            return False
        
        # Check for NO_COLOR environment variable
        import os
        if os.environ.get('NO_COLOR'):
            return False
        
        # Check for FORCE_COLOR environment variable
        if os.environ.get('FORCE_COLOR'):
            return True
        
        # On Windows, check for ANSICON or WT_SESSION (Windows Terminal)
        if sys.platform == 'win32':
            return bool(os.environ.get('ANSICON') or os.environ.get('WT_SESSION'))
        
        return True
    
    def _is_backend_log(self, record: logging.LogRecord) -> bool:
        """
        Check if the log record is from a backend component.
        
        Args:
            record: The log record to check
            
        Returns:
            True if this is a backend log, False otherwise
        """
        logger_name = record.name.lower()
        return any(keyword in logger_name for keyword in self.BACKEND_KEYWORDS)
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with colors.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string with color codes
        """
        if not self.use_colors:
            return super().format(record)
        
        # Save original values
        levelname_orig = record.levelname
        name_orig = record.name
        
        # Color the level name
        level_color = self.LEVEL_COLORS.get(record.levelno, '')
        record.levelname = f"{level_color}{record.levelname}{Colors.RESET}"
        
        # Color backend component names
        if self._is_backend_log(record):
            record.name = f"{Colors.BLUE}{record.name}{Colors.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original values
        record.levelname = levelname_orig
        record.name = name_orig
        
        return result


def setup_colored_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
    use_colors: bool = True
) -> None:
    """
    Configure colored logging for the application.
    
    This function sets up a colored console handler with the specified format.
    It should be called early in the application startup.
    
    Args:
        level: The logging level (default: INFO)
        format_string: Custom format string (default: includes timestamp, name, level, message)
        date_format: Custom date format string (default: ISO 8601 format)
        use_colors: Whether to use colors (default: True, auto-detects TTY support)
    
    Example:
        >>> from solace_agent_mesh.common.logging_config import setup_colored_logging
        >>> setup_colored_logging(level=logging.DEBUG)
    """
    # Default format includes timestamp, logger name, level, and message
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if date_format is None:
        date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create colored formatter
    formatter = ColoredFormatter(
        fmt=format_string,
        datefmt=date_format,
        use_colors=use_colors
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)


def get_colored_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    This is a convenience function that returns a logger instance.
    The logger will use the colored formatter if setup_colored_logging() has been called.
    
    Args:
        name: The logger name (typically __name__)
        level: Optional logging level for this specific logger
        
    Returns:
        A logger instance
        
    Example:
        >>> from solace_agent_mesh.common.logging_config import get_colored_logger
        >>> log = get_colored_logger(__name__)
        >>> log.info("This is an info message")
    """
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger