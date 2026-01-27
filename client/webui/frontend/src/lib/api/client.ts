import { getApiBearerToken } from "@/lib/utils/api";

interface RequestOptions {
    headers?: HeadersInit;
    signal?: AbortSignal;
    keepalive?: boolean;
    credentials?: RequestCredentials;
}

/* eslint-disable @typescript-eslint/no-explicit-any -- API responses vary; callers can specify types for safety */
interface HttpMethods {
    get: {
        <T = any>(endpoint: string, options?: RequestOptions): Promise<T>;
        (endpoint: string, options: RequestOptions & { fullResponse: true }): Promise<Response>;
    };
    post: {
        <T = any>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T>;
        (endpoint: string, body: unknown, options: RequestOptions & { fullResponse: true }): Promise<Response>;
    };
    put: {
        <T = any>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T>;
        (endpoint: string, body: unknown, options: RequestOptions & { fullResponse: true }): Promise<Response>;
    };
    delete: {
        <T = any>(endpoint: string, options?: RequestOptions): Promise<T>;
        (endpoint: string, options: RequestOptions & { fullResponse: true }): Promise<Response>;
    };
    patch: {
        <T = any>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T>;
        (endpoint: string, body: unknown, options: RequestOptions & { fullResponse: true }): Promise<Response>;
    };
    getFullUrl: (endpoint: string) => string;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

const getRefreshToken = () => localStorage.getItem("refresh_token");

const setTokens = (accessToken: string, samAccessToken: string, refreshToken: string) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    if (samAccessToken) {
        localStorage.setItem("sam_access_token", samAccessToken);
    } else {
        localStorage.removeItem("sam_access_token");
    }
};

const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("sam_access_token");
    localStorage.removeItem("refresh_token");
};

const refreshToken = async () => {
    // Don't attempt token refresh if we're in the middle of logging out
    if (sessionStorage.getItem("logout_in_progress") === "true") {
        return null;
    }

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
        setTokens(data.access_token, data.sam_access_token, data.refresh_token);
        return getApiBearerToken();
    }

    clearTokens();
    window.location.href = "/api/v1/auth/login";
    return null;
};

const getErrorFromResponse = async (response: Response): Promise<string> => {
    const fallbackMessage = `Request failed: ${response.statusText || `HTTP ${response.status}`}`;
    try {
        const text = await response.text();
        if (!text) return fallbackMessage;
        try {
            const errorData = JSON.parse(text);

            // Handle 422 validation errors with array format (FastAPI/Pydantic)
            if (response.status === 422 && errorData.detail && Array.isArray(errorData.detail)) {
                const validationErrors = errorData.detail
                    .map((err: { loc?: string[]; msg: string }) => {
                        const field = err.loc?.join(".") || "field";
                        return `${field}: ${err.msg}`;
                    })
                    .join(", ");
                return `Validation error: ${validationErrors}`;
            }

            // Handle standard error formats
            return errorData.message || errorData.detail || fallbackMessage;
        } catch {
            return text.length < 500 ? text : fallbackMessage;
        }
    } catch {
        return fallbackMessage;
    }
};

const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
    const bearerToken = getApiBearerToken();

    if (!bearerToken) {
        return fetch(url, options);
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            Authorization: `Bearer ${bearerToken}`,
        },
    });

    if (response.status === 401) {
        const newBearerToken = await refreshToken();
        if (newBearerToken) {
            return fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    Authorization: `Bearer ${newBearerToken}`,
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
    if (response.status === 204) {
        return undefined;
    }
    const text = await response.text();
    return text ? JSON.parse(text) : undefined;
};

type InternalRequestOptions = RequestOptions & RequestInit & { fullResponse?: boolean };

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

    private async request(baseUrl: string, endpoint: string, options?: InternalRequestOptions) {
        const url = `${baseUrl}${endpoint}`;
        const { fullResponse, ...fetchOptions } = options || {};

        if (fullResponse) {
            return authenticatedFetch(url, fetchOptions);
        }

        return fetchJsonWithError(url, fetchOptions);
    }

    private buildRequestWithBody(method: string, body: unknown, options?: InternalRequestOptions): InternalRequestOptions {
        if (body instanceof FormData) {
            return { ...options, method, body };
        }
        if (body === undefined || body === null) {
            return { ...options, method };
        }
        return {
            ...options,
            method,
            headers: { "Content-Type": "application/json", ...options?.headers },
            body: JSON.stringify(body),
        };
    }

    private createHttpMethods(getBaseUrl: () => string): HttpMethods {
        return {
            get: ((endpoint: string, options?: InternalRequestOptions) => this.request(getBaseUrl(), endpoint, options)) as HttpMethods["get"],

            post: ((endpoint: string, body?: unknown, options?: InternalRequestOptions) => this.request(getBaseUrl(), endpoint, this.buildRequestWithBody("POST", body, options))) as HttpMethods["post"],

            put: ((endpoint: string, body?: unknown, options?: InternalRequestOptions) => this.request(getBaseUrl(), endpoint, this.buildRequestWithBody("PUT", body, options))) as HttpMethods["put"],

            delete: ((endpoint: string, options?: InternalRequestOptions) => this.request(getBaseUrl(), endpoint, { ...options, method: "DELETE" })) as HttpMethods["delete"],

            patch: ((endpoint: string, body?: unknown, options?: InternalRequestOptions) => this.request(getBaseUrl(), endpoint, this.buildRequestWithBody("PATCH", body, options))) as HttpMethods["patch"],

            getFullUrl: (endpoint: string) => `${getBaseUrl()}${endpoint}`,
        };
    }
}

export const api = new ApiClient();
