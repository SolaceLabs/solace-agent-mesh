import re


def sanitize_name_for_filesystem(name: str) -> str:
    """
    Converts a registry name to a filesystem-safe format.
    Spaces and other problematic characters are converted to underscores,
    then normalized to a safe filesystem identifier.
    """
    if not name or not name.strip():
        return "unnamed_registry"

    # Normalize separators (spaces, hyphens, underscores) to underscores
    normalized = re.sub(r'[\s\-_]+', '_', name.strip())

    # Handle camelCase by inserting underscores before capital letters
    camel_case_split = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', normalized)

    # Handle acronyms by inserting underscores between them and following words
    acronym_split = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', camel_case_split)

    # Split and clean up the parts
    raw_parts = [p for p in acronym_split.split('_') if p]
    parts = [p.lower() for p in raw_parts]

    # Join with underscores for a filesystem-safe name
    result = "_".join(parts)

    # Ensure we have a valid result
    return result if result else "unnamed_registry"
