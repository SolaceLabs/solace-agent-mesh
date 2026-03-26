/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

expect.extend(matchers);

// Shared mock functions declared at module level for vi.doMock closures
const mockUseChatContext = vi.fn();
const mockUseTaskContext = vi.fn();
const mockUseTitleAnimation = vi.fn();
const mockUseConfigContext = vi.fn();
const mockUseIsChatSharingEnabled = vi.fn();
const mockUseProjectContext = vi.fn();
const mockUseLocation = vi.fn();
const mockUseNavigate = vi.fn();
const mockUseShareLink = vi.fn();
const mockUseShareUsers = vi.fn();

function makeDefaultChatContext(overrides: Record<string, unknown> = {}) {
    return {
        agents: [],
        sessionId: "session-1",
        sessionName: "Test Session",
        messages: [],
        isSidePanelCollapsed: true,
        setIsSidePanelCollapsed: vi.fn(),
        openSidePanelTab: vi.fn(),
        setTaskIdInSidePanel: vi.fn(),
        isResponding: false,
        latestStatusText: { current: null },
        isLoadingSession: false,
        sessionToDelete: null,
        closeSessionDeleteModal: vi.fn(),
        confirmSessionDelete: vi.fn(),
        currentTaskId: null,
        isCollaborativeSession: false,
        currentUserEmail: "user@example.com",
        sessionOwnerName: null,
        sessionOwnerEmail: null,
        handleSwitchSession: vi.fn(),
        ...overrides,
    };
}

function makeDefaultTaskContext() {
    return {
        isTaskMonitorConnected: true,
        isTaskMonitorConnecting: false,
        taskMonitorSseError: null,
        connectTaskMonitorStream: vi.fn(),
    };
}

describe("ChatPage", () => {
    let ChatPage: React.ComponentType;

    beforeEach(async () => {
        vi.resetModules();
        mockUseChatContext.mockReset();
        mockUseTaskContext.mockReset();
        mockUseTitleAnimation.mockReset();
        mockUseConfigContext.mockReset();
        mockUseIsChatSharingEnabled.mockReset();
        mockUseProjectContext.mockReset();
        mockUseLocation.mockReset();
        mockUseNavigate.mockReset();
        mockUseShareLink.mockReset();
        mockUseShareUsers.mockReset();

        // Default return values
        mockUseChatContext.mockReturnValue(makeDefaultChatContext());
        mockUseTaskContext.mockReturnValue(makeDefaultTaskContext());
        mockUseTitleAnimation.mockReturnValue({ text: "Test Session", isAnimating: false, isGenerating: false });
        mockUseConfigContext.mockReturnValue({ autoTitleGenerationEnabled: false });
        mockUseIsChatSharingEnabled.mockReturnValue(false);
        mockUseProjectContext.mockReturnValue({ activeProject: null });
        mockUseLocation.mockReturnValue({ pathname: "/chat", state: null });
        mockUseNavigate.mockReturnValue(vi.fn());
        mockUseShareLink.mockReturnValue({ data: null });
        mockUseShareUsers.mockReturnValue({ data: { users: [] } });

        vi.doMock("@/lib/hooks", () => ({
            useChatContext: mockUseChatContext,
            useTaskContext: mockUseTaskContext,
            useTitleAnimation: mockUseTitleAnimation,
            useConfigContext: mockUseConfigContext,
            useIsChatSharingEnabled: mockUseIsChatSharingEnabled,
        }));

        vi.doMock("@/lib/providers", () => ({
            useProjectContext: mockUseProjectContext,
        }));

        vi.doMock("react-router-dom", async () => {
            const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
            return {
                ...actual,
                useLocation: mockUseLocation,
                useNavigate: mockUseNavigate,
            };
        });

        vi.doMock("@/lib/api/share", () => ({
            useShareLink: mockUseShareLink,
            useShareUsers: mockUseShareUsers,
        }));

        vi.doMock("@tanstack/react-query", async () => {
            const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
            return {
                ...actual,
                useQueryClient: () => ({
                    invalidateQueries: vi.fn(),
                }),
            };
        });

        // Mock UI components - especially ResizablePanel which needs DOM measurements
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

        // Mock ChatMessageList from ui/chat
        vi.doMock("@/lib/components/ui/chat/chat-message-list", () => ({
            ChatMessageList: React.forwardRef<unknown, { children: React.ReactNode }>(function ChatMessageList({ children }) {
                return React.createElement("div", { "data-testid": "chat-message-list" }, children);
            }),
        }));

        // Mock heavy child components to isolate ChatPage behavior
        vi.doMock("@/lib/components/header", () => ({
            Header: ({ title, buttons, leadingAction }: { title: React.ReactNode; buttons?: React.ReactNode[]; leadingAction?: React.ReactNode }) => React.createElement("header", { "data-testid": "header" }, leadingAction, title, buttons),
        }));

        vi.doMock("@/lib/components/chat", () => ({
            ChatMessage: ({ message }: { message: { parts: Array<{ text?: string }> } }) => React.createElement("div", { "data-testid": "chat-message" }, message.parts?.[0]?.text || ""),
            ChatSessionDialog: () => React.createElement("div", { "data-testid": "chat-session-dialog" }),
            ChatSessionDeleteDialog: () => React.createElement("div", { "data-testid": "chat-session-delete-dialog" }),
            ChatSidePanel: () => React.createElement("div", { "data-testid": "chat-side-panel" }),
            ChatInputArea: () => React.createElement("div", { "data-testid": "chat-input-area" }),
            LoadingMessageRow: () => React.createElement("div", { "data-testid": "loading-message-row" }),
            ProjectBadge: ({ text }: { text: string }) => React.createElement("span", { "data-testid": "project-badge" }, text),
            SessionSidePanel: ({ onToggle }: { onToggle: () => void }) => React.createElement("div", { "data-testid": "session-side-panel", onClick: onToggle }),
            UserPresenceAvatars: () => React.createElement("div", { "data-testid": "user-presence-avatars" }),
            ShareNotificationMessage: () => React.createElement("div", { "data-testid": "share-notification" }),
        }));

        vi.doMock("@/lib/components/share/ShareButton", () => ({
            ShareButton: ({ onClick }: { onClick: () => void }) => React.createElement("button", { "data-testid": "share-button", onClick }, "Share"),
        }));

        vi.doMock("@/lib/components/share/ShareDialog", () => ({
            ShareDialog: () => React.createElement("div", { "data-testid": "share-dialog" }),
        }));

        vi.doMock("@/lib/api", () => ({
            api: {
                webui: { post: vi.fn() },
            },
        }));

        const mod = await import("@/lib/components/pages/ChatPage");
        ChatPage = mod.ChatPage;
    });

    function renderPage() {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        });
        return render(React.createElement(QueryClientProvider, { client: queryClient }, React.createElement(MemoryRouter, null, React.createElement(ChatPage))));
    }

    test("renders loading state when isLoadingSession is true", () => {
        mockUseChatContext.mockReturnValue(makeDefaultChatContext({ isLoadingSession: true }));

        renderPage();
        expect(screen.getByText("Loading session...")).toBeInTheDocument();
    });

    test("renders messages when loaded", () => {
        mockUseChatContext.mockReturnValue(
            makeDefaultChatContext({
                messages: [
                    { isUser: true, parts: [{ kind: "text", text: "Hello" }], taskId: "t1", metadata: { messageId: "m1" } },
                    { isUser: false, parts: [{ kind: "text", text: "Hi there" }], taskId: "t1", metadata: { messageId: "m2" } },
                ],
            })
        );

        renderPage();
        expect(screen.getAllByTestId("chat-message")).toHaveLength(2);
    });

    test("shows session side panel toggle button", () => {
        renderPage();
        expect(screen.getByTestId("showSessionsPanel")).toBeInTheDocument();
    });

    test("title animation displays session name", () => {
        mockUseTitleAnimation.mockReturnValue({ text: "My Custom Chat", isAnimating: false, isGenerating: false });

        renderPage();
        expect(screen.getByText("My Custom Chat")).toBeInTheDocument();
    });

    test("share button visible when chatSharingEnabled is true and sessionId exists", () => {
        mockUseIsChatSharingEnabled.mockReturnValue(true);
        mockUseChatContext.mockReturnValue(makeDefaultChatContext({ sessionId: "session-1" }));

        renderPage();
        expect(screen.getByTestId("share-button")).toBeInTheDocument();
    });

    test("share button hidden when chatSharingEnabled is false", () => {
        mockUseIsChatSharingEnabled.mockReturnValue(false);

        renderPage();
        expect(screen.queryByTestId("share-button")).not.toBeInTheDocument();
    });

    test("shows collaborative fork button when isCollaborativeSession is true", () => {
        mockUseIsChatSharingEnabled.mockReturnValue(true);
        mockUseChatContext.mockReturnValue(
            makeDefaultChatContext({
                sessionId: "session-1",
                isCollaborativeSession: true,
            })
        );

        renderPage();
        expect(screen.getByRole("button", { name: /Continue in New Chat/i })).toBeInTheDocument();
        // Share button should NOT be present for collaborative sessions
        expect(screen.queryByTestId("share-button")).not.toBeInTheDocument();
    });
});
