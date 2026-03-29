/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

const mockUseSharedSession = vi.fn();

describe("SharedChatViewPage", () => {
    let SharedChatViewPage: React.ComponentType;

    beforeEach(async () => {
        vi.resetModules();
        mockUseSharedSession.mockReset();

        vi.doMock("@/lib/hooks/useSharedSession", () => ({
            useSharedSession: mockUseSharedSession,
            formatDateYMD: (epochMs: number) => new Date(epochMs).toISOString().slice(0, 10),
        }));

        // Mock ChatMessage to avoid pulling in the full chat component tree
        vi.doMock("@/lib/components/chat", () => ({
            ChatMessage: () => React.createElement("div", { "data-testid": "chat-message" }),
        }));

        // Mock SharedSidePanel
        vi.doMock("@/lib/components/share/SharedSidePanel", () => ({
            SharedSidePanel: () => React.createElement("div", { "data-testid": "side-panel" }),
        }));

        // Mock SharedChatProvider to just pass through children
        vi.doMock("@/lib/providers/SharedChatProvider", () => ({
            SharedChatProvider: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
        }));

        // Mock Header component
        vi.doMock("@/lib/components/header", () => ({
            Header: ({ title }: { title: string }) => React.createElement("header", { "data-testid": "header" }, title),
        }));

        const mod = await import("@/lib/components/pages/SharedChatViewPage");
        SharedChatViewPage = mod.SharedChatViewPage;
    });

    function renderPage() {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        });
        return render(React.createElement(QueryClientProvider, { client: queryClient }, React.createElement(MemoryRouter, null, React.createElement(SharedChatViewPage))));
    }

    test("shows spinner when loading", () => {
        mockUseSharedSession.mockReturnValue({
            loading: true,
            error: null,
            session: null,
        });

        renderPage();
        expect(screen.getByText("Loading shared chat...")).toBeInTheDocument();
    });

    test("shows error message when there is an error", () => {
        mockUseSharedSession.mockReturnValue({
            loading: false,
            error: "Access denied",
            session: null,
            navigate: vi.fn(),
        });

        renderPage();
        expect(screen.getByText("Unable to View Shared Chat")).toBeInTheDocument();
        expect(screen.getByText("Access denied")).toBeInTheDocument();
    });

    test("shows not found state when session is null without error", () => {
        mockUseSharedSession.mockReturnValue({
            loading: false,
            error: null,
            session: null,
            navigate: vi.fn(),
        });

        renderPage();
        expect(screen.getByText("Shared Chat Not Found")).toBeInTheDocument();
    });
});
