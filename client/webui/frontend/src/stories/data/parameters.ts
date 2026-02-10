/**
 * Reusable parameter presets for Storybook stories and tests.
 * Import and spread these into your story/test parameters to avoid repetition.
 *
 * @example
 * // In a story
 * parameters: {
 *     ...withProjectSharingEnabled,
 *     ...asOwner("owner-user"),
 * },
 *
 * @example
 * // In a test
 * const Story = composeStory({
 *     args: { ... },
 *     parameters: {
 *         ...withProjectSharingEnabled,
 *         ...asOwner("owner-user"),
 *     },
 * }, meta);
 */

// ============================================================================
// Config Context Presets
// ============================================================================

export const withAuthorization = {
    configContext: {
        configUseAuthorization: true,
    },
};

// ============================================================================
// Auth Context Presets
// ============================================================================

export const asOwner = (username: string = "owner-user") => ({
    authContext: {
        userInfo: { username },
    },
});

export const asViewer = (username: string = "different-user") => ({
    authContext: {
        userInfo: { username },
    },
});

// ============================================================================
// Combined Presets
// ============================================================================

export const ownerWithAuthorization = (ownerUsername: string = "owner-user") => ({
    ...withAuthorization,
    ...asOwner(ownerUsername),
});

// ============================================================================
// Project Sharing Presets
// ============================================================================

export const withProjectSharingEnabled = {
    configContext: {
        configUseAuthorization: true,
        configFeatureEnablement: {
            projectSharingEnabled: true,
        },
    },
};

export const withIdentityService = (type: "okta" | "azure" | string = "okta") => ({
    configContext: {
        identityServiceType: type,
    },
});

export const withoutIdentityService = {
    configContext: {
        identityServiceType: null,
    },
};

export const ownerWithSharingEnabled = (ownerUsername: string = "owner-user") => ({
    ...withProjectSharingEnabled,
    ...asOwner(ownerUsername),
});

export const viewerWithSharingEnabled = (viewerUsername: string = "different-user") => ({
    ...withProjectSharingEnabled,
    ...asViewer(viewerUsername),
});
