import { getAccessToken } from "@/lib/utils/api";

interface RequestOptions extends RequestInit {
    raw?: boolean;
    keepalive?: boolean;
}

interface HttpMethods {
    get: (endpoint: string, options?: RequestOptions) => Promise<any>;
    post: (endpoint: string, body?: unknown, options?: RequestOptions) => Promise<any>;
    put: (endpoint: string, body?: unknown, options?: RequestOptions) => Promise<any>;
    delete: (endpoint: string, options?: RequestOptions) => Promise<any>;
    patch: (endpoint: string, body?: unknown, options?: RequestOptions) => Promise<any>;
    getFullUrl: (endpoint: string) => string;
}

const getRefreshToken = () => localStorage.getItem("refresh_token");

const setTokens = (accessToken: string, refreshToken: string) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
};

const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
};

const refreshToken = async () => {
    const token = getRefreshToken();
    if (!token) {
        return null;
    }

    const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
    });

    if (response.ok) {
        const data = await response.json();
        setTokens(data.access_token, data.refresh_token);
        return data.access_token;
    }

    clearTokens();
    window.location.href = "/api/v1/auth/login";
    return null;
};

const getErrorFromResponse = async (response: Response): Promise<string> => {
    const fallbackMessage = `An unknown error occurred. HTTP status: ${response.status}.`;
    try {
        const errorData = await response.json();
        return errorData.message || errorData.detail || fallbackMessage;
    } catch {
        return fallbackMessage;
    }
};

const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
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

const fetchWithError = async (url: string, options: RequestInit = {}) => {
    const response = await authenticatedFetch(url, options);

    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }

    return response;
};

const fetchJsonWithError = async (url: string, options: RequestInit = {}) => {
    const response = await fetchWithError(url, options);
    return response.json();
};

class ApiClient {
    private webuiBaseUrl = "";
    private platformBaseUrl = "";

    webui: HttpMethods;
    platform: HttpMethods;

    constructor() {
        this.webui = this.createHttpMethods(() => this.webuiBaseUrl);
        this.platform = this.createHttpMethods(() => this.platformBaseUrl);
    }

    configure(webuiUrl: string, platformUrl: string) {
        this.webuiBaseUrl = webuiUrl;
        this.platformBaseUrl = platformUrl;
    }

    private async request(baseUrl: string, endpoint: string, options?: RequestOptions) {
        const url = `${baseUrl}${endpoint}`;
        const { raw, keepalive, ...fetchOptions } = options || {};
        const finalOptions = keepalive ? { ...fetchOptions, keepalive } : fetchOptions;

        if (raw) {
            return fetchWithError(url, finalOptions);
        }

        return fetchJsonWithError(url, finalOptions);
    }

    private createHttpMethods(getBaseUrl: () => string): HttpMethods {
        return {
            get: (endpoint: string, options?: RequestOptions) =>
                this.request(getBaseUrl(), endpoint, options),

            post: (endpoint: string, body?: unknown, options?: RequestOptions) => {
                if (body instanceof FormData) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "POST",
                        body: body,
                    });
                }
                if (body === undefined || body === null) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "POST",
                    });
                }
                return this.request(getBaseUrl(), endpoint, {
                    ...options,
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...options?.headers,
                    },
                    body: JSON.stringify(body),
                });
            },

            put: (endpoint: string, body?: unknown, options?: RequestOptions) => {
                if (body instanceof FormData) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "PUT",
                        body: body,
                    });
                }
                if (body === undefined || body === null) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "PUT",
                    });
                }
                return this.request(getBaseUrl(), endpoint, {
                    ...options,
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        ...options?.headers,
                    },
                    body: JSON.stringify(body),
                });
            },

            delete: (endpoint: string, options?: RequestOptions) =>
                this.request(getBaseUrl(), endpoint, {
                    ...options,
                    method: "DELETE",
                }),

            patch: (endpoint: string, body?: unknown, options?: RequestOptions) => {
                if (body instanceof FormData) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "PATCH",
                        body: body,
                    });
                }
                if (body === undefined || body === null) {
                    return this.request(getBaseUrl(), endpoint, {
                        ...options,
                        method: "PATCH",
                    });
                }
                return this.request(getBaseUrl(), endpoint, {
                    ...options,
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        ...options?.headers,
                    },
                    body: JSON.stringify(body),
                });
            },

            getFullUrl: (endpoint: string) => `${getBaseUrl()}${endpoint}`,
        };
    }
}

export const api = new ApiClient();
