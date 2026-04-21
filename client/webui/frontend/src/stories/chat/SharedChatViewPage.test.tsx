/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

const mockUseSharedSession = vi.fn();
const mockUseConfigContext = vi.fn();

function makeValidSession(overrides: Record<string, unknown> = {}) {
    return {
        shareId: "share-1",
        navigate: vi.fn(),
        session: {
            title: "Test Shared Chat",
            tasks: [{ userId: "alice@example.com" }],
            createdTime: 0,
            snapshotTime: null,
            isOwner: false,
            sessionId: null,
        },
        loading: false,
        error: null,
        isForking: false,
        isSidePanelCollapsed: true,
        activeSidePanelTab: "files",
        setActiveSidePanelTab: vi.fn(),
        selectedTaskId: null,
        setSelectedTaskId: vi.fn(),
        toggleSidePanel: vi.fn(),
        openSidePanelTab: vi.fn(),
        convertedArtifacts: [],
        ragData: [],
        hasRagSources: false,
        messages: [],
        lastMessageIndexByTaskId: new Map(),
        sessionIdForProvider: "session-1",
        handleSharedArtifactDownload: vi.fn(),
        handleForkChat: vi.fn(),
        handleProviderTabOpen: vi.fn(),
        ...overrides,
    };
}

describe("SharedChatViewPage", () => {
    let SharedChatViewPage: React.ComponentType;

    beforeEach(async () => {
        vi.resetModules();
        mockUseSharedSession.mockReset();
        mockUseConfigContext.mockReset();
        mockUseConfigContext.mockReturnValue({});

        vi.doMock("@/lib/hooks/useSharedSession", () => ({
            useSharedSession: mockUseSharedSession,
            formatDateYMD: (epochMs: number) => new Date(epochMs).toISOString().slice(0, 10),
        }));

        vi.doMock("@/lib/hooks", async () => {
            const actual = await vi.importActual<typeof import("@/lib/hooks")>("@/lib/hooks");
            return {
                ...actual,
                useConfigContext: mockUseConfigContext,
            };
        });

        // Mock chat components — include SessionSidePanel so the flag-gate tests can assert its presence
        vi.doMock("@/lib/components/chat", () => ({
            ChatMessage: () => React.createElement("div", { "data-testid": "chat-message" }),
            SessionSidePanel: ({ onToggle }: { onToggle: () => void }) => React.createElement("div", { "data-testid": "session-side-panel", onClick: onToggle }),
        }));

        // Mock SharedSidePanel
        vi.doMock("@/lib/components/share/SharedSidePanel", () => ({
            SharedSidePanel: () => React.createElement("div", { "data-testid": "side-panel" }),
        }));

        // Mock SharedChatProvider to just pass through children
        vi.doMock("@/lib/providers/SharedChatProvider", () => ({
            SharedChatProvider: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
        }));

        // Mock Header — render leadingAction so the toggle button is findable in tests
        vi.doMock("@/lib/components/header", () => ({
            Header: ({ title, leadingAction }: { title: string; leadingAction?: React.ReactNode }) => React.createElement("header", { "data-testid": "header" }, leadingAction, title),
        }));

        // Neutralize ResizablePanel* — their real impl needs DOM measurements that jsdom can't provide
        vi.doMock("@/lib/components/ui", async () => {
            const actual = await vi.importActual<Record<string, unknown>>("@/lib/components/ui");
            return {
                ...actual,
                ResizablePanelGroup: ({ children }: { children: React.ReactNode }) => React.createElement("div", { "data-testid": "resizable-panel-group" }, children),
                ResizablePanel: React.forwardRef<unknown, { children: React.ReactNode }>(function ResizablePanel({ children }) {
                    return React.createElement("div", { "data-testid": "resizable-panel" }, children);
                }),
                ResizableHandle: () => React.createElement("div", { "data-testid": "resizable-handle" }),
            };
        });

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

    test("hides SessionSidePanel and toggle button when newNavigation flag is enabled", () => {
        mockUseSharedSession.mockReturnValue(makeValidSession());
        mockUseConfigContext.mockReturnValue({ configFeatureEnablement: { newNavigation: true } });

        renderPage();
        expect(screen.queryByTestId("session-side-panel")).not.toBeInTheDocument();
        expect(screen.queryByTestId("showSessionsPanel")).not.toBeInTheDocument();
    });

    test("renders SessionSidePanel and toggle button when newNavigation flag is disabled", () => {
        mockUseSharedSession.mockReturnValue(makeValidSession());
        mockUseConfigContext.mockReturnValue({ configFeatureEnablement: { newNavigation: false } });

        renderPage();
        expect(screen.getByTestId("session-side-panel")).toBeInTheDocument();
        expect(screen.getByTestId("showSessionsPanel")).toBeInTheDocument();
    });
});
