import { fetchJsonWithError, fetchWithError } from "@/lib/utils/api";

interface HttpMethods {
    get: (endpoint: string) => Promise<any>;
    post: (endpoint: string, body?: unknown, options?: RequestInit) => Promise<any>;
    put: (endpoint: string, body?: unknown, options?: RequestInit) => Promise<any>;
    delete: (endpoint: string, options?: RequestInit) => Promise<any>;
    patch: (endpoint: string, body?: unknown, options?: RequestInit) => Promise<any>;
}

class ApiClient {
    private webuiBaseUrl = "";
    private platformBaseUrl = "";
    private configured = false;
    private baseUrlsCache: { webui: string; platform: string } | null = null;

    webui: HttpMethods;
    platform: HttpMethods;

    constructor() {
        this.webui = this.createHttpMethods(() => this.webuiBaseUrl);
        this.platform = this.createHttpMethods(() => this.platformBaseUrl);
    }

    configure(webuiUrl: string, platformUrl: string) {
        if (this.configured && (this.webuiBaseUrl !== webuiUrl || this.platformBaseUrl !== platformUrl)) {
            console.warn('[API Client] Reconfiguring with different URLs:', {
                old: { webui: this.webuiBaseUrl, platform: this.platformBaseUrl },
                new: { webui: webuiUrl, platform: platformUrl },
            });
        }
        this.webuiBaseUrl = webuiUrl;
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

    private createHttpMethods(getBaseUrl: () => string): HttpMethods {
        return {
            get: (endpoint: string) => this.request(getBaseUrl(), endpoint),

            post: (endpoint: string, body?: unknown, options?: RequestInit) => {
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

            put: (endpoint: string, body?: unknown, options?: RequestInit) => {
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

            delete: (endpoint: string, options?: RequestInit) =>
                this.request(getBaseUrl(), endpoint, {
                    ...options,
                    method: "DELETE",
                }),

            patch: (endpoint: string, body?: unknown, options?: RequestInit) => {
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
        };
    }

    getBaseUrls() {
        this.ensureConfigured();
        if (!this.baseUrlsCache) {
            this.baseUrlsCache = {
                webui: this.webuiBaseUrl,
                platform: this.platformBaseUrl,
            };
        }
        return this.baseUrlsCache;
    }
}

export const api = new ApiClient();
