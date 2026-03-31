/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, test, expect, beforeEach, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

describe("FeatureFlagProvider", () => {
    let FeatureFlagProvider: React.ComponentType<{ children: React.ReactNode }>;
    let mockWebuiGet: ReturnType<typeof vi.fn>;
    let mockSetProvider: ReturnType<typeof vi.fn>;
    let queryClient: QueryClient;

    const makeFeaturesResponse = (flags: Record<string, boolean>) =>
        new Response(JSON.stringify(Object.entries(flags).map(([key, resolved]) => ({ key, resolved, name: key, release_phase: "ga", has_env_override: false, registry_default: false, description: "" }))), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });

    const makeErrorResponse = (status: number) => new Response("Error", { status });

    beforeEach(async () => {
        vi.resetModules();

        mockWebuiGet = vi.fn();
        mockSetProvider = vi.fn();
        queryClient = new QueryClient({ defaultOptions: { queries: { retry: 0 } } });

        vi.doMock("@/lib/api", () => ({
            api: { webui: { get: mockWebuiGet } },
        }));

        vi.doMock("@openfeature/react-sdk", async () => {
            const actual = await vi.importActual<typeof import("@openfeature/react-sdk")>("@openfeature/react-sdk");
            return {
                ...actual,
                OpenFeature: { ...actual.OpenFeature, setProvider: mockSetProvider },
            };
        });

        const mod = await import("@/lib/providers/FeatureFlagProvider");
        FeatureFlagProvider = mod.FeatureFlagProvider;
    });

    const renderWithQuery = (ui: React.ReactElement) => render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);

    test("renders children immediately without waiting for feature flags", async () => {
        mockWebuiGet.mockReturnValue(new Promise(() => {})); // never resolves

        renderWithQuery(
            <FeatureFlagProvider>
                <div data-testid="child">Hello</div>
            </FeatureFlagProvider>
        );

        expect(screen.getByTestId("child")).toBeInTheDocument();
    });

    test("calls setProvider with resolved flags after successful fetch", async () => {
        mockWebuiGet.mockResolvedValue(makeFeaturesResponse({ my_feature: true, other_feature: false }));

        renderWithQuery(
            <FeatureFlagProvider>
                <div data-testid="child">Hello</div>
            </FeatureFlagProvider>
        );

        await waitFor(() => {
            expect(mockSetProvider).toHaveBeenCalledOnce();
        });

        const providerArg = mockSetProvider.mock.calls[0][0];
        expect(providerArg.resolveBooleanEvaluation("my_feature", false)).toEqual({ value: true, reason: "STATIC" });
        expect(providerArg.resolveBooleanEvaluation("other_feature", true)).toEqual({ value: false, reason: "STATIC" });
    });

    test("calls setProvider with empty flags when features endpoint returns an error", async () => {
        mockWebuiGet.mockResolvedValue(makeErrorResponse(503));

        renderWithQuery(
            <FeatureFlagProvider>
                <div data-testid="child">Hello</div>
            </FeatureFlagProvider>
        );

        await waitFor(() => {
            expect(mockSetProvider).toHaveBeenCalledOnce();
        });

        const providerArg = mockSetProvider.mock.calls[0][0];
        expect(providerArg.resolveBooleanEvaluation("any_flag", true)).toEqual({ value: true, reason: "DEFAULT" });
    });

    test("calls setProvider with empty flags when fetch throws", async () => {
        mockWebuiGet.mockRejectedValue(new Error("network error"));

        renderWithQuery(
            <FeatureFlagProvider>
                <div data-testid="child">Hello</div>
            </FeatureFlagProvider>
        );

        await waitFor(() => {
            expect(mockSetProvider).toHaveBeenCalledOnce();
        });

        const providerArg = mockSetProvider.mock.calls[0][0];
        expect(providerArg.resolveBooleanEvaluation("any_flag", true)).toEqual({ value: true, reason: "DEFAULT" });
    });
});
