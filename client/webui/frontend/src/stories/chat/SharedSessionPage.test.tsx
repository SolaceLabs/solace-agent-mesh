/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

const mockUseSharedSession = vi.fn();

describe("SharedSessionPage", () => {
    let SharedSessionPage: React.ComponentType;

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

        const mod = await import("@/lib/components/pages/SharedSessionPage");
        SharedSessionPage = mod.SharedSessionPage;
    });

    function renderPage() {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        });
        return render(React.createElement(QueryClientProvider, { client: queryClient }, React.createElement(MemoryRouter, null, React.createElement(SharedSessionPage))));
    }

    test("shows spinner when loading", () => {
        mockUseSharedSession.mockReturnValue({
            loading: true,
            error: null,
            session: null,
        });

        renderPage();
        expect(screen.getByText("Loading shared session...")).toBeInTheDocument();
    });

    test("shows error message when there is an error", () => {
        mockUseSharedSession.mockReturnValue({
            loading: false,
            error: "Session access denied",
            session: null,
            navigate: vi.fn(),
        });

        renderPage();
        expect(screen.getByText("Unable to View Shared Session")).toBeInTheDocument();
        expect(screen.getByText("Session access denied")).toBeInTheDocument();
    });

    test("shows not found state when session is null without error", () => {
        mockUseSharedSession.mockReturnValue({
            loading: false,
            error: null,
            session: null,
            navigate: vi.fn(),
        });

        renderPage();
        expect(screen.getByText("Shared Session Not Found")).toBeInTheDocument();
    });

    function makeLoadedSession(overrides: Record<string, unknown> = {}) {
        return {
            loading: false,
            error: null,
            session: {
                title: "My Shared Session",
                createdTime: 1700000000000,
                snapshotTime: null,
                tasks: [{ userId: "alice@example.com" }],
            },
            messages: [
                {
                    isUser: true,
                    parts: [{ kind: "text", text: "Hello" }],
                    taskId: "task-1",
                    metadata: { messageId: "msg-1" },
                },
                {
                    isUser: false,
                    parts: [{ kind: "text", text: "Hi there" }],
                    taskId: "task-1",
                    metadata: { messageId: "msg-2" },
                },
            ],
            lastMessageIndexByTaskId: new Map([["task-1", 1]]),
            navigate: vi.fn(),
            shareId: "share-123",
            sessionIdForProvider: "session-456",
            convertedArtifacts: [],
            ragData: {},
            handleProviderTabOpen: vi.fn(),
            setSelectedTaskId: vi.fn(),
            selectedTaskId: null,
            isSidePanelCollapsed: false,
            activeSidePanelTab: "files",
            setActiveSidePanelTab: vi.fn(),
            toggleSidePanel: vi.fn(),
            openSidePanelTab: vi.fn(),
            hasRagSources: false,
            handleSharedArtifactDownload: vi.fn(),
            handleForkChat: vi.fn(),
            isForking: false,
            ...overrides,
        };
    }

    test("renders session title and messages when loaded", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession());

        renderPage();
        expect(screen.getByText("My Shared Session")).toBeInTheDocument();
        expect(screen.getAllByTestId("chat-message")).toHaveLength(2);
    });

    test("renders fork button (Continue in New Chat)", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession());

        renderPage();
        expect(screen.getByRole("button", { name: /Continue in New Chat/i })).toBeInTheDocument();
    });

    test("fork button click triggers handleForkChat", async () => {
        const handleForkChat = vi.fn();
        mockUseSharedSession.mockReturnValue(makeLoadedSession({ handleForkChat }));

        renderPage();
        const forkButton = screen.getByRole("button", { name: /Continue in New Chat/i });
        forkButton.click();
        expect(handleForkChat).toHaveBeenCalledTimes(1);
    });

    test("renders side panel", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession());

        renderPage();
        expect(screen.getByTestId("side-panel")).toBeInTheDocument();
    });

    test("read-only banner is shown", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession());

        renderPage();
        expect(screen.getByText("This chat is read-only. To build off of it, continue a new conversation.")).toBeInTheDocument();
    });

    test("shows shared-by info when no snapshot time", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession());

        renderPage();
        expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    });

    test("shows snapshot date when snapshotTime is present", () => {
        const session = makeLoadedSession();
        (session.session as Record<string, unknown>).snapshotTime = 1700000000000;
        mockUseSharedSession.mockReturnValue(session);

        renderPage();
        expect(screen.getByText(/Snapshot from/)).toBeInTheDocument();
    });

    test("shows empty state when there are no messages", () => {
        mockUseSharedSession.mockReturnValue(makeLoadedSession({ messages: [] }));

        renderPage();
        expect(screen.getByText("No messages in this session.")).toBeInTheDocument();
    });
});
