"""
Minimal asyncio fix for macOS subprocess creation issues.

This module provides a targeted fix for the NotImplementedError that occurs when
creating subprocesses with asyncio on macOS with Python 3.11+.

The issue occurs because the default event loop policy on macOS doesn't implement
get_child_watcher(), which is required for subprocess creation.
"""

import logging
import sys

log = logging.getLogger(__name__)


def apply_macos_asyncio_fix() -> bool:
    """
    Apply minimal asyncio fix for macOS subprocess support.

    This fix specifically addresses the NotImplementedError in
    asyncio.events.get_child_watcher() by providing a ThreadedChildWatcher
    implementation that works on macOS.

    Returns:
        bool: True if fix was applied or not needed, False if fix failed.
    """
    if sys.platform != "darwin" and sys.platform != "linux":
        log.debug("Not on macOS or linux, asyncio fix not needed.")
        return True

    import asyncio

    log.info(
        "On macOS. Applying asyncio child watcher fix for Python %s",
        sys.version.split()[0],
    )

    try:
        import asyncio.events
        from asyncio.unix_events import ThreadedChildWatcher

        if not hasattr(asyncio.events, "_original_get_child_watcher_by_solace_fix"):
            if hasattr(asyncio.events.get_child_watcher, "__name__") and (
                asyncio.events.get_child_watcher.__name__ == "get_child_watcher"
                or asyncio.events.get_child_watcher.__name__
                == "patched_get_child_watcher"
            ):
                asyncio.events._original_get_child_watcher_by_solace_fix = (
                    asyncio.events.get_child_watcher
                )

        def patched_get_child_watcher():
            """Returns a ThreadedChildWatcher that works on macOS."""
            return ThreadedChildWatcher()

        asyncio.events.get_child_watcher = patched_get_child_watcher

        test_watcher = asyncio.events.get_child_watcher()
        log.info(
            "Successfully applied asyncio fix. get_child_watcher is now patched to use %s.",
            type(test_watcher).__name__,
        )
        return True

    except ImportError as e_imp:
        log.error(
            "Failed to import necessary asyncio modules for macOS fix: %s. This is unexpected.",
            e_imp,
        )
        return False
    except Exception as e:
        log.error("Failed to apply unconditional asyncio fix for macOS: %s", e)
        return False


def ensure_asyncio_compatibility():
    """
    Ensure asyncio compatibility for subprocess creation on macOS.
    This function should be called as early as possible in the application.

    Returns:
        bool: True if compatibility is ensured, False otherwise.
    """
    return apply_macos_asyncio_fix()


ensure_asyncio_compatibility()
