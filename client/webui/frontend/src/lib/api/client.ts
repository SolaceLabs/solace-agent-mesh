import { fetchJsonWithError, fetchWithError } from "@/lib/utils/api";

class ApiClient {
    private chatBaseUrl = "";
    private platformBaseUrl = "";
    private configured = false;
    private baseUrlsCache: { chat: string; platform: string } | null = null;

    configure(chatUrl: string, platformUrl: string) {
        if (this.configured && (this.chatBaseUrl !== chatUrl || this.platformBaseUrl !== platformUrl)) {
            console.warn('[API Client] Reconfiguring with different URLs:', {
                old: { chat: this.chatBaseUrl, platform: this.platformBaseUrl },
                new: { chat: chatUrl, platform: platformUrl },
            });
        }
        this.chatBaseUrl = chatUrl;
        this.platformBaseUrl = platformUrl;
        this.configured = true;
        this.baseUrlsCache = null;
    }

    private ensureConfigured() {
        if (!this.configured) {
            throw new Error("API client not configured. Call api.configure() from ConfigProvider first.");
        }
    }

    private async request(baseUrl: string, endpoint: string, options?: RequestInit) {
        this.ensureConfigured();
        const url = `${baseUrl}${endpoint}`;

        if (options?.body && typeof options.body !== "string" && !(options.body instanceof FormData)) {
            return fetchWithError(url, options);
        }

        return fetchJsonWithError(url, options);
    }

    chat = {
        get: (endpoint: string) => this.request(this.chatBaseUrl, endpoint),

        post: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.chatBaseUrl, endpoint, {
                    ...options,
                    method: "POST",
                });
            }
            return this.request(this.chatBaseUrl, endpoint, {
                ...options,
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },

        put: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.chatBaseUrl, endpoint, {
                    ...options,
                    method: "PUT",
                });
            }
            return this.request(this.chatBaseUrl, endpoint, {
                ...options,
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },

        delete: (endpoint: string, options?: RequestInit) =>
            this.request(this.chatBaseUrl, endpoint, {
                ...options,
                method: "DELETE",
            }),

        patch: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.chatBaseUrl, endpoint, {
                    ...options,
                    method: "PATCH",
                });
            }
            return this.request(this.chatBaseUrl, endpoint, {
                ...options,
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },
    };

    platform = {
        get: (endpoint: string) => this.request(this.platformBaseUrl, endpoint),

        post: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.platformBaseUrl, endpoint, {
                    ...options,
                    method: "POST",
                });
            }
            return this.request(this.platformBaseUrl, endpoint, {
                ...options,
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },

        put: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.platformBaseUrl, endpoint, {
                    ...options,
                    method: "PUT",
                });
            }
            return this.request(this.platformBaseUrl, endpoint, {
                ...options,
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },

        delete: (endpoint: string, options?: RequestInit) =>
            this.request(this.platformBaseUrl, endpoint, {
                ...options,
                method: "DELETE",
            }),

        patch: (endpoint: string, body?: any, options?: RequestInit) => {
            if (body === undefined || body === null) {
                return this.request(this.platformBaseUrl, endpoint, {
                    ...options,
                    method: "PATCH",
                });
            }
            return this.request(this.platformBaseUrl, endpoint, {
                ...options,
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    ...options?.headers,
                },
                body: JSON.stringify(body),
            });
        },
    };

    getBaseUrls() {
        this.ensureConfigured();
        if (!this.baseUrlsCache) {
            this.baseUrlsCache = {
                chat: this.chatBaseUrl,
                platform: this.platformBaseUrl,
            };
        }
        return this.baseUrlsCache;
    }
}

export const api = new ApiClient();
