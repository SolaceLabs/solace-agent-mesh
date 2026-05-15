/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

const mockUseSharedSession = vi.fn();
let newNavigationFlag = false;

async function loadPage() {
    vi.resetModules();

    vi.doMock("@/lib/hooks/useSharedSession", () => ({
        useSharedSession: mockUseSharedSession,
        formatDateYMD: (epochMs: number) => new Date(epochMs).toISOString().slice(0, 10),
    }));

    vi.doMock("@/lib/components/chat", () => ({
        ChatMessage: () => React.createElement("div", { "data-testid": "chat-message" }),
        SessionSidePanel: () => React.createElement("aside", { "data-testid": "session-side-panel" }),
    }));

    vi.doMock("@/lib/components/share/SharedSidePanel", () => ({
        SharedSidePanel: () => React.createElement("div", { "data-testid": "side-panel" }),
    }));

    vi.doMock("@/lib/providers/SharedChatProvider", () => ({
        SharedChatProvider: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
    }));

    vi.doMock("@/lib/components/header", () => ({
        Header: ({ title }: { title: string }) => React.createElement("header", { "data-testid": "header" }, title),
    }));

    vi.doMock("@/lib/hooks", () => ({
        useIsNewNavigationEnabled: () => newNavigationFlag,
    }));

    const mod = await import("@/lib/components/pages/SharedChatViewPage");
    return mod.SharedChatViewPage;
}

describe("SharedChatViewPage", () => {
    let SharedChatViewPage: React.ComponentType;

    beforeEach(async () => {
        mockUseSharedSession.mockReset();
        newNavigationFlag = false;
        SharedChatViewPage = await loadPage();
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

    function loadedSessionMock() {
        return {
            loading: false,
            error: null,
            session: {
                title: "My Shared Chat",
                createdTime: 1_700_000_000_000,
                snapshotTime: null,
                tasks: [{ userId: "alice" }],
                isOwner: false,
                sessionId: null,
            },
            navigate: vi.fn(),
            convertedArtifacts: [],
            ragData: [],
            sessionIdForProvider: "sid",
            shareId: "share-1",
            handleProviderTabOpen: vi.fn(),
            setSelectedTaskId: vi.fn(),
            messages: [],
            lastMessageIndexByTaskId: new Map<string, number>(),
            isSidePanelCollapsed: true,
            activeSidePanelTab: "workflow",
            setActiveSidePanelTab: vi.fn(),
            toggleSidePanel: vi.fn(),
            openSidePanelTab: vi.fn(),
            hasRagSources: false,
            handleSharedArtifactDownload: vi.fn(),
            selectedTaskId: null,
            isForking: false,
            handleForkChat: vi.fn(),
        };
    }

    test("renders SessionSidePanel when newNavigation flag is off", async () => {
        newNavigationFlag = false;
        SharedChatViewPage = await loadPage();
        mockUseSharedSession.mockReturnValue(loadedSessionMock());

        renderPage();
        expect(screen.getByTestId("session-side-panel")).toBeInTheDocument();
    });

    test("omits SessionSidePanel when newNavigation flag is on", async () => {
        newNavigationFlag = true;
        SharedChatViewPage = await loadPage();
        mockUseSharedSession.mockReturnValue(loadedSessionMock());

        renderPage();
        expect(screen.queryByTestId("session-side-panel")).not.toBeInTheDocument();
    });
});
