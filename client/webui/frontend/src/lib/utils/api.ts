export const getAccessToken = () => localStorage.getItem("access_token");

export const getErrorMessage = (error: unknown, fallbackMessage: string = "An unknown error occurred"): string => {
    if (error instanceof Error) {
        return error.message ?? fallbackMessage;
    }
    return fallbackMessage;
};
