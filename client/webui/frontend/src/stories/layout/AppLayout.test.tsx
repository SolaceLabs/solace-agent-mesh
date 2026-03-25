/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import React from "react";

import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

// ---- Mocks must be declared before the dynamic import ----

// Mock ChatProvider to pass-through so StoryProvider's MockChatProvider values reach AppLayoutContent.
vi.mock("@/lib/providers", () => ({
    ChatProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock useModelConfigStatus hook
const mockModelConfigStatus = vi.fn<() => { data: { configured: boolean } | undefined }>();
vi.mock("@/lib/api/models", () => ({
    useModelConfigStatus: () => mockModelConfigStatus(),
}));

// Mock useLocalStorage to avoid side-effects
vi.mock("@/lib/hooks/useLocalStorage", () => ({
    useLocalStorage: (_key: string, initial: unknown) => [initial, vi.fn()],
}));

// Lazy import so all mocks are in place
const { default: AppLayout } = await import("@/AppLayout");

function renderLayout(chatContextValues = {}, featureFlags: Record<string, boolean> = {}) {
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={chatContextValues} configContextValues={{ configFeatureEnablement: featureFlags }}>
                <AppLayout />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("AppLayout model warning banner", () => {
    describe("when model_config_ui flag is disabled", () => {
        beforeEach(() => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
        });

        test("does not show warning", () => {
            renderLayout();
            expect(screen.queryByText(/No model has been set up/)).not.toBeInTheDocument();
        });
    });

    describe("when model_config_ui flag is enabled", () => {
        test("does not show warning when models are configured", () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: true } });
            renderLayout({}, { model_config_ui: true });
            expect(screen.queryByText(/No model has been set up/)).not.toBeInTheDocument();
        });

        test("does not show warning when status is still loading", () => {
            mockModelConfigStatus.mockReturnValue({ data: undefined });
            renderLayout({}, { model_config_ui: true });
            expect(screen.queryByText(/No model has been set up/)).not.toBeInTheDocument();
        });

        test("shows warning when models not configured", () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            renderLayout({}, { model_config_ui: true });
            expect(screen.getByText(/No model has been set up/)).toBeInTheDocument();
        });

        test("shows Go to Models button when user has write permission", () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            renderLayout({ hasModelConfigWrite: true }, { model_config_ui: true });
            // Banner and dialog may both show a "Go to Models" button
            const buttons = screen.getAllByRole("button", { name: /Go to Models/i });
            expect(buttons.length).toBeGreaterThanOrEqual(1);
            expect(screen.queryByText(/Contact your administrator/)).not.toBeInTheDocument();
        });

        test("shows contact admin text when user lacks write permission", () => {
            mockModelConfigStatus.mockReturnValue({ data: { configured: false } });
            renderLayout({ hasModelConfigWrite: false }, { model_config_ui: true });
            expect(screen.getByText(/Contact your administrator/)).toBeInTheDocument();
            expect(screen.queryByRole("button", { name: /Go to Models/i })).not.toBeInTheDocument();
        });
    });
});
