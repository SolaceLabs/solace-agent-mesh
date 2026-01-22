export const getAccessToken = () => localStorage.getItem("access_token");

export const getSamAccessToken = () => localStorage.getItem("sam_access_token");

export const getApiBearerToken = (): string | null => {
    // Prefer SAM access token if available
    const samToken = getSamAccessToken();

    if (samToken) {
        return samToken;
    }
    // Fallback to general access token
    return getAccessToken();
}

export const getErrorMessage = (error: unknown, fallbackMessage: string = "An unknown error occurred"): string => {
    if (error instanceof Error) {
        return error.message ?? fallbackMessage;
    }
    return fallbackMessage;
};
