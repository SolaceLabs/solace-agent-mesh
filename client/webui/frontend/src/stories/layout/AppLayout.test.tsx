/// <reference types="@testing-library/jest-dom" />
import { screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import React from "react";

import { renderWithProviders } from "@/lib/test-utils";
import * as modelsApi from "@/lib/api/models";
import AppLayout from "@/AppLayout";

expect.extend(matchers);

// ---- Mocks must be declared before the dynamic import ----

// Mock useNotificationSSE to avoid EventSource (not available in Node.js test env)
vi.mock("@/lib/hooks/useNotificationSSE", () => ({
    useNotificationSSE: () => {},
}));

// Mock ChatProvider to pass-through so StoryProvider's MockChatProvider values reach AppLayoutContent.
vi.mock("@/lib/providers", () => ({
    ChatProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock useLocalStorage to avoid side-effects
vi.mock("@/lib/hooks/useLocalStorage", () => ({
    useLocalStorage: (_key: string, initial: unknown) => [initial, vi.fn()],
}));

const mockModelConfigStatus = vi.fn<() => { data: { configured: boolean } | undefined }>();

beforeEach(() => {
    vi.spyOn(modelsApi, "useModelConfigStatus").mockImplementation((() => mockModelConfigStatus()) as unknown as typeof modelsApi.useModelConfigStatus);
});

describe("AppLayout model warning banner", () => {
    describe("when model_config_ui flag is disabled", () => {
        beforeEach(() => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        });

        test("does not show warning", async () => {
            await renderWithProviders(<AppLayout />);
            expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
        });
    });

    describe("when model_config_ui flag is enabled", () => {
        test("does not show warning when models are configured", async () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: true } });
            await renderWithProviders(<AppLayout />, { featureFlags: { model_config_ui: true } });
            expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
        });

        test("does not show warning when status is still loading", async () => {
            mockModelConfigStatus.mockReturnValue({ data: undefined });
            await renderWithProviders(<AppLayout />, { featureFlags: { model_config_ui: true } });
            expect(screen.queryByText(/Default models have not been configured/)).not.toBeInTheDocument();
        });

        test("shows warning when models not configured", async () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            await renderWithProviders(<AppLayout />, { featureFlags: { model_config_ui: true } });
            expect(screen.getByText(/Default models have not been configured/)).toBeInTheDocument();
        });

        test("shows Go to Models button when user has write permission", async () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            await renderWithProviders(<AppLayout />, {
                featureFlags: { model_config_ui: true },
                chatContextValues: { hasModelConfigWrite: true },
            });
            // Banner and dialog may both show a "Go to Models" button
            await waitFor(() => {
                const buttons = screen.getAllByRole("button", { name: /Go to Models/i });
                expect(buttons.length).toBeGreaterThanOrEqual(1);
            });
            expect(screen.queryByText(/Ask your administrator/)).not.toBeInTheDocument();
        });

        test("shows contact admin text when user lacks write permission", async () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            await renderWithProviders(<AppLayout />, {
                featureFlags: { model_config_ui: true },
                chatContextValues: { hasModelConfigWrite: false },
            });
            expect(screen.getByText(/Ask your administrator/)).toBeInTheDocument();
            expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
        });
    });
});
