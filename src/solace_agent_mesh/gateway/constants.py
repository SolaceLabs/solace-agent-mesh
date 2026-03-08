"""
Shared constants for the HTTP/SSE gateway.

This module contains configuration defaults that are shared across
multiple components to avoid duplication and ensure consistency.
"""

# ===== ARTIFACT AND MESSAGE SIZE LIMITS =====

ARTIFACTS_PREFIX = 'artifacts/'
DEFAULT_MAX_ARTIFACT_RESOLVE_SIZE_BYTES = 104857600  # 100MB - max size for artifact content embeds

DEFAULT_GATEWAY_RECURSIVE_EMBED_DEPTH = 12  # Maximum depth for resolving artifact_content embeds
DEFAULT_GATEWAY_MAX_MESSAGE_SIZE_BYTES = 10_000_000  # 10MB - max message size for gateway publishing

# ===== FILE UPLOAD SIZE LIMITS =====

DEFAULT_MAX_PER_FILE_UPLOAD_SIZE_BYTES = 52428800  # 50MB - per-file upload limit
DEFAULT_MAX_BATCH_UPLOAD_SIZE_BYTES = 104857600  # 100MB - batch upload limit (sum of files in one upload)
DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 104857600  # 100MB - ZIP import limit
DEFAULT_MAX_PROJECT_SIZE_BYTES = 104857600  # 100MB - total project size limit

# ===== FIELD LENGTH LIMITS =====

DEFAULT_MAX_PROJECT_FILE_DESCRIPTION_LENGTH = 1000  # max characters for file/artifact descriptions
