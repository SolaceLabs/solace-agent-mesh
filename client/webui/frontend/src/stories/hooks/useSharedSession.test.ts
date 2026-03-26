/**
 * Tests for useSharedSession hook — shared session data fetching, message parsing,
 * artifact conversion, and action handlers.
 */
import { renderHook, act } from "@testing-library/react";
import { describe, test, expect, beforeEach, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import type { SharedSessionView, SharedArtifact } from "@/lib/types/share";

/** Helper: create a QueryClientProvider wrapper for renderHook */
function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
        },
    });
    return function Wrapper({ children }: { children: React.ReactNode }) {
        return createElement(QueryClientProvider, { client: queryClient }, children);
    };
}

// Shared mock references
let mockNavigate: ReturnType<typeof vi.fn>;
let mockShareId: string;
let mockSessionQueryReturn: Record<string, unknown>;
let mockForkMutateAsync: ReturnType<typeof vi.fn>;
let mockForkMutationReturn: Record<string, unknown>;
let mockDownloadSharedArtifact: ReturnType<typeof vi.fn>;

function buildSessionView(overrides?: Partial<SharedSessionView>): SharedSessionView {
    return {
        shareId: "share-abc",
        title: "Test Session",
        createdTime: 1700000000000,
        accessType: "public",
        tasks: [],
        artifacts: [],
        ...overrides,
    };
}

function buildArtifact(overrides?: Partial<SharedArtifact>): SharedArtifact {
    return {
        filename: "report.pdf",
        mimeType: "application/pdf",
        size: 1024,
        lastModified: "2024-01-15T10:00:00Z",
        version: 1,
        versionCount: 1,
        description: "A report",
        source: "agent-1",
        ...overrides,
    };
}

describe("useSharedSession", () => {
    let useSharedSession: typeof import("@/lib/hooks/useSharedSession").useSharedSession;
    let formatDateYMD: typeof import("@/lib/hooks/useSharedSession").formatDateYMD;

    beforeEach(async () => {
        vi.resetModules();

        mockNavigate = vi.fn();
        mockShareId = "share-abc";
        mockForkMutateAsync = vi.fn();
        mockDownloadSharedArtifact = vi.fn().mockResolvedValue(new Blob(["content"]));

        mockSessionQueryReturn = {
            data: undefined,
            isLoading: false,
            error: null,
        };

        mockForkMutationReturn = {
            mutateAsync: mockForkMutateAsync,
            isPending: false,
        };

        vi.doMock("react-router-dom", () => ({
            useParams: () => ({ shareId: mockShareId }),
            useNavigate: () => mockNavigate,
        }));

        vi.doMock("@/lib/api/share", () => ({
            useSharedSessionView: () => mockSessionQueryReturn,
            useForkSharedChat: () => mockForkMutationReturn,
            downloadSharedArtifact: mockDownloadSharedArtifact,
        }));

        vi.doMock("@/lib/utils/download", () => ({
            downloadBlob: vi.fn(),
        }));

        const mod = await import("@/lib/hooks/useSharedSession");
        useSharedSession = mod.useSharedSession;
        formatDateYMD = mod.formatDateYMD;
    });

    describe("loading state", () => {
        test("returns loading=true when query is loading", () => {
            mockSessionQueryReturn = { data: undefined, isLoading: true, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.loading).toBe(true);
            expect(result.current.session).toBeNull();
            expect(result.current.error).toBeNull();
        });
    });

    describe("error state", () => {
        test("returns error message when query fails with Error instance", () => {
            mockSessionQueryReturn = {
                data: undefined,
                isLoading: false,
                error: new Error("Network timeout"),
            };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.error).toBe("Network timeout");
            expect(result.current.loading).toBe(false);
        });

        test("returns fallback error message for non-Error errors", () => {
            mockSessionQueryReturn = {
                data: undefined,
                isLoading: false,
                error: "some string error",
            };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.error).toBe("Failed to load shared session");
        });
    });

    describe("session data", () => {
        test("returns session data when loaded", () => {
            const session = buildSessionView({ title: "My Shared Chat" });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.session).toEqual(session);
            expect(result.current.shareId).toBe("share-abc");
            expect(result.current.loading).toBe(false);
            expect(result.current.error).toBeNull();
        });
    });

    describe("convertedArtifacts", () => {
        test("maps SharedArtifact[] to ArtifactInfo[]", () => {
            const artifacts: SharedArtifact[] = [buildArtifact({ filename: "file1.txt", mimeType: "text/plain", size: 100 }), buildArtifact({ filename: "file2.pdf", mimeType: "application/pdf", size: 2048, version: 3, versionCount: 5 })];
            const session = buildSessionView({ artifacts });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.convertedArtifacts).toHaveLength(2);
            expect(result.current.convertedArtifacts[0]).toMatchObject({
                filename: "file1.txt",
                mime_type: "text/plain",
                size: 100,
            });
            expect(result.current.convertedArtifacts[1]).toMatchObject({
                filename: "file2.pdf",
                mime_type: "application/pdf",
                size: 2048,
                version: 3,
                versionCount: 5,
            });
        });

        test("returns empty array when no artifacts", () => {
            const session = buildSessionView({ artifacts: [] });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.convertedArtifacts).toEqual([]);
        });
    });

    describe("messages", () => {
        test("parses task messageBubbles into MessageFE[] format", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [
                            {
                                id: "msg-1",
                                type: "user",
                                text: "Hello",
                                parts: [{ kind: "text", text: "Hello" }],
                            },
                            {
                                id: "msg-2",
                                type: "agent",
                                text: "Hi there",
                                parts: [{ kind: "text", text: "Hi there" }],
                                senderDisplayName: "Bot",
                            },
                        ] as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.messages).toHaveLength(2);

            const userMsg = result.current.messages[0];
            expect(userMsg.isUser).toBe(true);
            expect(userMsg.role).toBe("user");
            expect(userMsg.taskId).toBe("task-1");
            expect(userMsg.parts).toEqual([{ kind: "text", text: "Hello" }]);

            const agentMsg = result.current.messages[1];
            expect(agentMsg.isUser).toBe(false);
            expect(agentMsg.role).toBe("agent");
            expect(agentMsg.senderDisplayName).toBe("Bot");
        });

        test("uses workflowTaskId when available", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        workflowTaskId: "workflow-task-99",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [
                            {
                                id: "msg-1",
                                type: "user",
                                parts: [{ kind: "text", text: "Test" }],
                            },
                        ] as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.messages[0].taskId).toBe("workflow-task-99");
        });

        test("handles string messageBubbles by parsing JSON", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: JSON.stringify([{ id: "msg-1", type: "user", parts: [{ kind: "text", text: "Parsed" }] }]) as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.messages).toHaveLength(1);
            expect(result.current.messages[0].parts).toEqual([{ kind: "text", text: "Parsed" }]);
        });

        test("falls back to bubble.text when parts is absent", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [{ id: "msg-1", type: "agent", text: "Fallback text" }] as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.messages[0].parts).toEqual([{ kind: "text", text: "Fallback text" }]);
        });
    });

    describe("ragData", () => {
        test("extracts RAG data from task metadata", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [],
                        taskMetadata: {
                            schema_version: 1,
                            rag_data: [{ source: "doc1.pdf", content: "relevant content", score: 0.95 }],
                        },
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.ragData).toHaveLength(1);
            expect(result.current.ragData[0]).toMatchObject({ source: "doc1.pdf", content: "relevant content" });
        });

        test("returns empty array when no tasks have RAG data", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [],
                        taskMetadata: null,
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.ragData).toEqual([]);
        });
    });

    describe("handleSharedArtifactDownload", () => {
        test("calls downloadSharedArtifact with shareId and filename", async () => {
            const session = buildSessionView();
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            await act(async () => {
                await result.current.handleSharedArtifactDownload({
                    filename: "report.pdf",
                    mime_type: "application/pdf",
                    size: 1024,
                    last_modified: "2024-01-01",
                });
            });

            expect(mockDownloadSharedArtifact).toHaveBeenCalledWith("share-abc", "report.pdf");
        });
    });

    describe("handleForkChat", () => {
        test("calls fork mutation and navigates to /chat", async () => {
            const session = buildSessionView();
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };
            mockForkMutateAsync.mockResolvedValue({ sessionId: "new-session-123" });

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            await act(async () => {
                await result.current.handleForkChat();
            });

            expect(mockForkMutateAsync).toHaveBeenCalledWith("share-abc");
            expect(mockNavigate).toHaveBeenCalledWith("/chat");
        });

        test("dispatches events after forking", async () => {
            vi.useFakeTimers();
            const session = buildSessionView();
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };
            mockForkMutateAsync.mockResolvedValue({ sessionId: "new-session-456" });

            const dispatchSpy = vi.spyOn(window, "dispatchEvent");

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            await act(async () => {
                await result.current.handleForkChat();
            });

            // Advance past the 200ms setTimeout
            await act(async () => {
                vi.advanceTimersByTime(250);
            });

            const eventTypes = dispatchSpy.mock.calls.map(call => (call[0] as CustomEvent).type);
            expect(eventTypes).toContain("new-chat-session");
            expect(eventTypes).toContain("switch-to-session");

            const switchEvent = dispatchSpy.mock.calls.find(call => (call[0] as CustomEvent).type === "switch-to-session");
            expect((switchEvent![0] as CustomEvent).detail).toEqual({ sessionId: "new-session-456" });

            dispatchSpy.mockRestore();
            vi.useRealTimers();
        });

        test("does not fork when already forking", async () => {
            const session = buildSessionView();
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };
            mockForkMutationReturn = { mutateAsync: mockForkMutateAsync, isPending: true };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            await act(async () => {
                await result.current.handleForkChat();
            });

            expect(mockForkMutateAsync).not.toHaveBeenCalled();
        });
    });

    describe("lastMessageIndexByTaskId", () => {
        test("correctly maps task IDs to last message index", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [
                            { id: "msg-1", type: "user", parts: [{ kind: "text", text: "Q1" }] },
                            { id: "msg-2", type: "agent", parts: [{ kind: "text", text: "A1" }] },
                        ] as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                    {
                        id: "task-2",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000001000,
                        messageBubbles: [
                            { id: "msg-3", type: "user", parts: [{ kind: "text", text: "Q2" }] },
                            { id: "msg-4", type: "agent", parts: [{ kind: "text", text: "A2" }] },
                        ] as unknown as import("@/lib/types/storage").MessageBubble[],
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            // task-1 has messages at index 0 and 1, so last is 1
            expect(result.current.lastMessageIndexByTaskId.get("task-1")).toBe(1);
            // task-2 has messages at index 2 and 3, so last is 3
            expect(result.current.lastMessageIndexByTaskId.get("task-2")).toBe(3);
        });
    });

    describe("hasRagSources", () => {
        test("is true when ragData is non-empty", () => {
            const session = buildSessionView({
                tasks: [
                    {
                        id: "task-1",
                        sessionId: "session-1",
                        userId: "user-1",
                        createdTime: 1700000000000,
                        messageBubbles: [],
                        taskMetadata: {
                            schema_version: 1,
                            rag_data: [{ source: "doc.pdf", content: "data" }],
                        },
                    },
                ],
            });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.hasRagSources).toBe(true);
        });

        test("is false when ragData is empty", () => {
            const session = buildSessionView({ tasks: [] });
            mockSessionQueryReturn = { data: session, isLoading: false, error: null };

            const { result } = renderHook(() => useSharedSession(), { wrapper: createWrapper() });

            expect(result.current.hasRagSources).toBe(false);
        });
    });

    describe("formatDateYMD", () => {
        test("formats epoch ms as a date string", () => {
            // formatDateYMD delegates to formatTimestamp with "date" format,
            // which calls toLocaleDateString(). We just verify it returns a non-empty string.
            const result = formatDateYMD(1700000000000);
            expect(typeof result).toBe("string");
            expect(result.length).toBeGreaterThan(0);
            expect(result).not.toBe("N/A");
        });
    });
});
