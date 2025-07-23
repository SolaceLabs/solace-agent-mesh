export const getAccessToken = () => {
    return localStorage.getItem("access_token");
};

const getRefreshToken = () => {
    return localStorage.getItem("refresh_token");
};

const setTokens = (accessToken: string, refreshToken: string) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
};

const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
};

const refreshToken = async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
        return null;
    }

    const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (response.ok) {
        const data = await response.json();
        setTokens(data.access_token, data.refresh_token);
        return data.access_token;
    }

    // If refresh fails, clear tokens and force re-login
    clearTokens();
    window.location.href = "/api/v1/auth/login";
    return null;
};

export const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
    const accessToken = getAccessToken();

    if (!accessToken) {
        return fetch(url, options);
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${accessToken}`,
        },
    });

    if (response.status === 401) {
        const newAccessToken = await refreshToken();
        if (newAccessToken) {
            return fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    Authorization: `Bearer ${newAccessToken}`,
                },
            });
        }
    }

    return response;
};
