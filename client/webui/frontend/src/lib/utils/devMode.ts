const DEV_USER_ID_KEY = "dev_user_id";

/**
 * Get the stored development user ID from localStorage
 * @returns The stored user_id or null if not set
 */
export const getDevUserId = (): string | null => {
    return localStorage.getItem(DEV_USER_ID_KEY);
};

/**
 * Store a development user ID in localStorage
 * @param userId - The user_id to store
 */
export const setDevUserId = (userId: string): void => {
    localStorage.setItem(DEV_USER_ID_KEY, userId);
};

/**
 * Remove the stored development user ID from localStorage
 */
export const clearDevUserId = (): void => {
    localStorage.removeItem(DEV_USER_ID_KEY);
};

/**
 * Check if development mode is active (user_id is set)
 * @returns true if a dev user_id is set, false otherwise
 */
export const isDevModeActive = (): boolean => {
    const userId = getDevUserId();
    return userId !== null && userId.trim() !== "";
};