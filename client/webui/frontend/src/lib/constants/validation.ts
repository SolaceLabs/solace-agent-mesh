/**
 * Default validation limits for frontend forms
 * These are fallback values used when backend validation limits are unavailable
 * Actual limits are fetched from backend via ConfigContext.validationLimits
 */

export const DEFAULT_MAX_NAME_LENGTH = 255;
export const DEFAULT_MAX_DESCRIPTION_LENGTH = 1000;
export const DEFAULT_MAX_INSTRUCTIONS_LENGTH = 4000;
