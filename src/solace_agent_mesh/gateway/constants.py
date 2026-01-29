"""
Shared constants for the HTTP/SSE gateway.

This module contains configuration defaults that are shared across
multiple components to avoid duplication and ensure consistency.
"""

# ===== ARTIFACT AND MESSAGE SIZE LIMITS =====

# Artifact prefix
ARTIFACTS_PREFIX = 'artifacts/'

# Artifact content resolution limits
DEFAULT_MAX_ARTIFACT_RESOLVE_SIZE_BYTES = 104857600  # 100MB - max size for artifact content embeds

# Recursive embed resolution limits
DEFAULT_GATEWAY_RECURSIVE_EMBED_DEPTH = 12  # Maximum depth for resolving artifact_content embeds

# Message size limits
DEFAULT_GATEWAY_MAX_MESSAGE_SIZE_BYTES = 10_000_000  # 10MB - max message size for gateway publishing

# ===== FILE UPLOAD SIZE LIMITS =====

# Production defaults
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 52428800  # 50MB - per-file upload limit
DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 104857600  # 100MB - ZIP import limit
DEFAULT_MAX_TOTAL_UPLOAD_SIZE_BYTES = 104857600  # 100MB - total project limit
