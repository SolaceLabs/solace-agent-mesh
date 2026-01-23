/**
 * Default validation limits for frontend forms
 * These are fallback values used when backend validation limits are unavailable
 * Actual limits are fetched from backend via ConfigContext.validationLimits
 */

// Project field limits (should match backend Pydantic models)
export const DEFAULT_PROJECT_NAME_MAX = 255;
export const DEFAULT_PROJECT_DESCRIPTION_MAX = 1000;
export const DEFAULT_PROJECT_INSTRUCTIONS_MAX = 4000;

// File upload limits
export const DEFAULT_MAX_UPLOAD_SIZE_BYTES = 52428800; // 50MB
export const DEFAULT_MAX_ZIP_UPLOAD_SIZE_BYTES = 104857600; // 100MB
