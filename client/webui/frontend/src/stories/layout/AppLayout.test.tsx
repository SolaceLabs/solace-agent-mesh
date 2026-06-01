/// <reference types="@testing-library/jest-dom" />
import { screen, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import React from "react";

import { renderWithProviders } from "@/lib/test-utils";
import * as modelsApi from "@/lib/api/models";
import { ChatSurfaceContext, type ChatSurface } from "@/lib/contexts";
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

const EMBEDDED_SURFACE: ChatSurface = {
    variant: "embedded",
    navigation: ["recentChats"],
    showAgentSelector: false,
    showActivityPanel: false,
    allowPrompts: false,
    allowMentions: true,
    pinnedAgent: "WeatherAgent",
    seedWelcomeBubble: false,
    sessionActions: ["rename", "renameWithAI", "delete"],
};

describe("AppLayout navigation gating by chat surface", () => {
    beforeEach(() => {
        mockModelConfigStatus.mockReturnValue({ data: { configured: true } });
    });

    test("embedded + new_navigation renders the collapsible sidebar with Recent Chats but no New Chat / app nav (issue #1)", async () => {
        await renderWithProviders(
            <ChatSurfaceContext.Provider value={EMBEDDED_SURFACE}>
                <AppLayout />
            </ChatSurfaceContext.Provider>,
            { featureFlags: { new_navigation: true } }
        );
        expect(screen.getByTestId("collapsible-navigation-sidebar")).toBeInTheDocument();
        expect(screen.getByText("Recent Chats")).toBeInTheDocument();
        // New Chat button and app nav items are suppressed in recent-chats-only mode.
        expect(screen.queryByText("New Chat")).not.toBeInTheDocument();
        // The legacy icon rail is never shown alongside the new nav.
        expect(screen.queryByTestId("navigation-sidebar")).not.toBeInTheDocument();
    });

    test("embedded + legacy nav renders no sidebar (the icon rail has no Recent Chats)", async () => {
        await renderWithProviders(
            <ChatSurfaceContext.Provider value={EMBEDDED_SURFACE}>
                <AppLayout />
            </ChatSurfaceContext.Provider>,
            { featureFlags: { new_navigation: false } }
        );
        expect(screen.queryByTestId("navigation-sidebar")).not.toBeInTheDocument();
        expect(screen.queryByTestId("collapsible-navigation-sidebar")).not.toBeInTheDocument();
    });

    test("full surface shows the full collapsible nav (incl. New Chat) when new_navigation is enabled", async () => {
        await renderWithProviders(<AppLayout />, { featureFlags: { new_navigation: true } });
        expect(screen.getByTestId("collapsible-navigation-sidebar")).toBeInTheDocument();
        expect(screen.getByText("New Chat")).toBeInTheDocument();
    });

    test("full surface still shows the legacy nav when new_navigation is disabled", async () => {
        await renderWithProviders(<AppLayout />, { featureFlags: { new_navigation: false } });
        expect(screen.getByTestId("navigation-sidebar")).toBeInTheDocument();
    });
});
