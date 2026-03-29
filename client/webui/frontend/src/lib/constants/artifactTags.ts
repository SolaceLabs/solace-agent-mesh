/**
 * Frontend constants matching backend system tag definitions.
 * System tags are prefixed with "__" to distinguish from user tags.
 */

// System artifact tags (must match backend constants in common/constants.py)
export const ARTIFACT_TAG_USER_UPLOADED = "__user_uploaded";
export const ARTIFACT_TAG_WORKING = "__working";

// Shared localStorage key for the "show working/internal artifacts" toggle
export const SHOW_WORKING_ARTIFACTS_STORAGE_KEY = "sam_show_working_artifacts";

/**
 * Checks if an artifact has the working system tag (case-insensitive).
 * Working artifacts are hidden from users by default.
 */
export function hasWorkingTag(tags: string[] | undefined): boolean {
    return tags?.some(t => t.toLowerCase() === ARTIFACT_TAG_WORKING.toLowerCase()) ?? false;
}
