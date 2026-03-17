import { getApiBearerToken, getSamAccessToken } from "@/lib/utils/api";

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
    // Schedule proactive refresh whenever tokens are set (login, callback, refresh).
    // All const declarations in this module are initialized before any runtime calls
    // to setTokens(), so scheduleProactiveRefresh is safe to reference here.
    scheduleProactiveRefresh();
};

const clearTokens = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("sam_access_token");
    localStorage.removeItem("refresh_token");
    cancelProactiveRefresh();
};

// Shared promise to deduplicate concurrent refresh attempts.
// Multiple simultaneous 401s will all await the same refresh call.
let pendingRefresh: Promise<string | null> | null = null;

// --- Proactive token refresh ---
// Refresh tokens ~5 minutes before they expire to avoid 401 storms,
// especially for long-lived SSE connections that can't retry easily.
const PROACTIVE_REFRESH_MARGIN_MS = 5 * 60 * 1000; // 5 minutes
const MIN_PROACTIVE_REFRESH_DELAY_MS = 30 * 1000; // 30 seconds — prevents tight loops with short-TTL tokens
let proactiveRefreshTimer: ReturnType<typeof setTimeout> | null = null;

/** Decode the `exp` claim from a JWT without verifying the signature. */
const getTokenExpMs = (token: string | null): number | null => {
    if (!token) return null;
    try {
        const payload = token.split(".")[1];
        if (!payload) return null;
        // Convert base64url → standard base64 before decoding.
        // JWTs use base64url encoding which replaces + with - and / with _.
        const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
        const decoded = JSON.parse(atob(base64));
        if (typeof decoded.exp === "number") {
            return decoded.exp * 1000; // seconds → ms
        }
    } catch {
        // Not a JWT or malformed — ignore
    }
    return null;
};

/**
 * Schedule a proactive token refresh based on the earliest expiring token.
 * Called after every successful token set (login, callback, refresh).
 */
const scheduleProactiveRefresh = () => {
    if (proactiveRefreshTimer) {
        clearTimeout(proactiveRefreshTimer);
        proactiveRefreshTimer = null;
    }

    // Check both token types and pick the earliest expiration
    const samExp = getTokenExpMs(getSamAccessToken());
    const accessExp = getTokenExpMs(localStorage.getItem("access_token"));
    const expirations = [samExp, accessExp].filter((e): e is number => e !== null);

    if (expirations.length === 0) return;

    const earliestExp = Math.min(...expirations);
    const now = Date.now();
    const delay = earliestExp - now - PROACTIVE_REFRESH_MARGIN_MS;

    if (delay <= 0) {
        // Already within the refresh margin — schedule with minimum delay floor
        // to prevent tight loops when tokens have very short TTLs or clock skew.
        const floorDelay = MIN_PROACTIVE_REFRESH_DELAY_MS;
        console.debug(`[api/client] Token near expiry, scheduling proactive refresh in ${floorDelay / 1000}s`);
        proactiveRefreshTimer = setTimeout(() => {
            proactiveRefreshTimer = null;
            console.debug("[api/client] Proactive token refresh triggered (near-expiry)");
            void refreshToken();
        }, floorDelay);
        return;
    }

    console.debug(`[api/client] Scheduling proactive token refresh in ${Math.round(delay / 1000)}s`);
    proactiveRefreshTimer = setTimeout(() => {
        proactiveRefreshTimer = null;
        console.debug("[api/client] Proactive token refresh triggered");
        void refreshToken();
    }, delay);
};

/** Cancel any pending proactive refresh (e.g. on logout). */
const cancelProactiveRefresh = () => {
    if (proactiveRefreshTimer) {
        clearTimeout(proactiveRefreshTimer);
        proactiveRefreshTimer = null;
    }
};

const refreshToken = async () => {
    // Check abort conditions before joining any in-flight refresh, so a logout
    // initiated mid-refresh doesn't let new callers receive a fresh token.
    if (sessionStorage.getItem("logout_in_progress") === "true") {
        return null;
    }

    const token = getRefreshToken();
    if (!token) {
        return null;
    }

    if (pendingRefresh) {
        return pendingRefresh;
    }

    pendingRefresh = (async () => {
        const response = await fetch("/api/v1/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: token }),
        });

        if (response.ok) {
            const data = await response.json();
            // setTokens() internally calls scheduleProactiveRefresh()
            setTokens(data.access_token, data.sam_access_token, data.refresh_token);
            return getApiBearerToken();
        }

        clearTokens();
        globalThis.location.href = "/api/v1/auth/login";
        return null;
    })()
        .catch(() => null)
        .finally(() => {
            pendingRefresh = null;
        });

    return pendingRefresh;
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
            const retryResponse = await fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    Authorization: `Bearer ${newBearerToken}`,
                },
            });

            // If the retry after a successful refresh still returns 401, the new
            // token is also being rejected (e.g. persistent server-side issue).
            // Redirect to login to break any external retry loop.
            if (retryResponse.status === 401) {
                clearTokens();
                globalThis.location.href = "/api/v1/auth/login";
                // Navigation is async — return the 401 as-is; the page will
                // navigate away before callers can act on it.
                return retryResponse;
            }

            return retryResponse;
        }
        // refreshToken() returned null — it already cleared tokens and redirected
        // to login (or there was no refresh token). Return the 401 as-is.
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
export { getErrorFromResponse, refreshToken, scheduleProactiveRefresh, cancelProactiveRefresh };
