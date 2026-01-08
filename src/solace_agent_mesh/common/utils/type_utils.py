"""
Utilities for robust type checking, especially in development environments.
"""
import inspect


def is_subclass_by_name(cls_to_check: type, base_class_name: str) -> bool:
    """
    Checks if a class is a subclass of another class by looking for the
    base class's name in the Method Resolution Order (MRO).

    This is a robust workaround for development environments where the same
    class might be loaded from two different paths (e.g., from 'src' and
    from an editable install in 'site-packages'), causing standard
    `issubclass()` checks to fail.

    Args:
        cls_to_check: The class to inspect.
        base_class_name: The string name of the base class to look for.

    Returns:
        True if the base class name is found in the ancestry, False otherwise.
    """
    if not inspect.isclass(cls_to_check):
        return False

    # Check the name of each class in the inheritance chain
    return any(base.__name__ == base_class_name for base in cls_to_check.__mro__)
