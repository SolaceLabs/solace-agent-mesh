/**
 * Centralized sessionStorage key constants used across redirect flows.
 * Prevents silent breakage from typos when keys are shared between components.
 */
export const SESSION_STORAGE_KEYS = {
    REDIRECT_PENDING_INPUT: "sam_redirect_pending_input",
    REDIRECT_CONTEXT: "sam_redirect_context",
    REDIRECT_SESSION_ID: "sam_redirect_session_id",
    REDIRECT_ARTIFACTS: "sam_redirect_artifacts",
} as const;
