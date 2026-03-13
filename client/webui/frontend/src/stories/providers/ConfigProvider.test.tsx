/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, test, expect, beforeEach, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

const mockConfigData = {
    frontend_server_url: "http://webui",
    frontend_platform_server_url: "http://platform",
    frontend_auth_login_url: "/login",
    frontend_use_authorization: false,
    frontend_welcome_message: "Welcome",
    frontend_redirect_url: "/",
    frontend_collect_feedback: false,
    frontend_bot_name: "Bot",
    frontend_logo_url: "/logo.png",
    persistence_enabled: false,
    identity_service_type: null,
};

const mockFeaturesData = [
    { key: "my_feature", name: "My Feature", release_phase: "ga", resolved: true, has_env_override: false, registry_default: false, description: "" },
    { key: "other_feature", name: "Other", release_phase: "beta", resolved: false, has_env_override: false, registry_default: false, description: "" },
];

describe("ConfigProvider", () => {
    let ConfigProvider: React.ComponentType<{ children: React.ReactNode }>;
    let mockSetProviderAndWait: ReturnType<typeof vi.fn>;
    let mockFetchCsrfToken: ReturnType<typeof vi.fn>;
    let mockWebuiGet: ReturnType<typeof vi.fn>;
    let mockApiConfigure: ReturnType<typeof vi.fn>;

    beforeEach(async () => {
        vi.resetModules();

        mockSetProviderAndWait = vi.fn().mockResolvedValue(undefined);
        mockFetchCsrfToken = vi.fn().mockResolvedValue(null);
        mockWebuiGet = vi.fn();
        mockApiConfigure = vi.fn();

        vi.doMock("@openfeature/react-sdk", () => ({
            OpenFeature: { setProviderAndWait: mockSetProviderAndWait },
            OpenFeatureProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
        }));

        vi.doMock("@/lib/hooks/useCsrfContext", () => ({
            useCsrfContext: () => ({
                fetchCsrfToken: mockFetchCsrfToken,
                clearCsrfToken: vi.fn(),
            }),
        }));

        vi.doMock("@/lib/api", () => ({
            api: {
                webui: { get: mockWebuiGet },
                configure: mockApiConfigure,
            },
        }));

        vi.doMock("@/lib/components", () => ({
            EmptyState: ({ title }: { title: string }) => React.createElement("div", null, title),
        }));

        const mod = await import("@/lib/providers/ConfigProvider");
        ConfigProvider = mod.ConfigProvider;
    });

    function makeOkResponse(data: unknown) {
        return new Response(JSON.stringify(data), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    }

    function makeErrorResponse(status: number, body = "Error") {
        return new Response(body, { status });
    }

    describe("successful initialization", () => {
        test("renders children after config and features load successfully", async () => {
            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeOkResponse(mockConfigData);
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("child")).toBeInTheDocument();
            });
        });

        test("passes feature flags from /config/features to OpenFeature provider", async () => {
            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeOkResponse(mockConfigData);
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("child")).toBeInTheDocument();
            });

            expect(mockSetProviderAndWait).toHaveBeenCalledOnce();
            const providerArg = mockSetProviderAndWait.mock.calls[0][0];
            expect(providerArg.resolveBooleanEvaluation("my_feature", false)).toEqual({ value: true, reason: "STATIC" });
            expect(providerArg.resolveBooleanEvaluation("other_feature", true)).toEqual({ value: false, reason: "STATIC" });
        });

        test("configures api client with server URLs from config response", async () => {
            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeOkResponse(mockConfigData);
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("child")).toBeInTheDocument();
            });

            expect(mockApiConfigure).toHaveBeenCalledWith("http://webui", "http://platform");
        });
    });

    describe("features endpoint degradation", () => {
        test("renders children with empty feature flags when features endpoint is unavailable", async () => {
            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeOkResponse(mockConfigData);
                return makeErrorResponse(503);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("child")).toBeInTheDocument();
            });

            expect(mockSetProviderAndWait).toHaveBeenCalledOnce();
            const providerArg = mockSetProviderAndWait.mock.calls[0][0];
            expect(providerArg.resolveBooleanEvaluation("any_flag", true)).toEqual({ value: true, reason: "DEFAULT" });
        });
    });

    describe("config fetch error handling", () => {
        test("shows error state when config fetch fails with non-403 status", async () => {
            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeErrorResponse(500);
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByText("Configuration Error")).toBeInTheDocument();
            });
        });
    });

    describe("CSRF retry on 403", () => {
        test("retries both config and features with CSRF token after initial 403", async () => {
            mockFetchCsrfToken.mockResolvedValue("csrf-token-xyz");
            let configCallCount = 0;

            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") {
                    configCallCount++;
                    if (configCallCount === 1) return makeErrorResponse(403, "Forbidden");
                    return makeOkResponse(mockConfigData);
                }
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByTestId("child")).toBeInTheDocument();
            });

            expect(mockFetchCsrfToken).toHaveBeenCalled();
            expect(configCallCount).toBe(2);
        });

        test("shows error state when CSRF retry config fetch also fails", async () => {
            mockFetchCsrfToken.mockResolvedValue("csrf-token-xyz");

            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeErrorResponse(403, "Forbidden");
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByText("Configuration Error")).toBeInTheDocument();
            });
        });

        test("shows error state when CSRF token cannot be obtained after 403", async () => {
            mockFetchCsrfToken.mockResolvedValue(null);

            mockWebuiGet.mockImplementation(async (endpoint: string) => {
                if (endpoint === "/api/v1/config") return makeErrorResponse(403, "Forbidden");
                return makeOkResponse(mockFeaturesData);
            });

            render(
                <ConfigProvider>
                    <div data-testid="child">Hello</div>
                </ConfigProvider>
            );

            await waitFor(() => {
                expect(screen.getByText("Configuration Error")).toBeInTheDocument();
            });
        });
    });
});
