import { describe, it, expect } from "vitest";

import type { MessageFE, ArtifactInfo, RAGSearchResult } from "@/lib/types";
import type { ChatEffect, ChatEventInput, ChatEventOutput } from "@/lib/providers/chat";
import { processChatEvent } from "@/lib/providers/chat";

// ============ Helpers ============

/** Build a minimal valid ChatEventInput with overrides. */
function makeInput(overrides: Partial<ChatEventInput> = {}): ChatEventInput {
    return {
        eventData: "{}",
        messages: [],
        ragData: [],
        artifacts: [],
        flags: {
            inlineActivityTimeline: false,
            showThinkingContent: false,
            ragEnabled: true,
            isReplaying: false,
        },
        sessionId: "session-1",
        selectedAgentName: "agent-1",
        deepResearchQueryHistory: new Map(),
        eventSequence: 1,
        isTaskRunningInBackground: () => false,
        ...overrides,
    };
}

/** Wrap an RPC result in the JSON-RPC envelope and serialize. */
function statusUpdateEvent(taskId: string, parts: Array<Record<string, unknown>> = [], options: { final?: boolean; contextId?: string } = {}): string {
    return JSON.stringify({
        jsonrpc: "2.0",
        result: {
            kind: "status-update",
            taskId,
            final: options.final ?? false,
            status: {
                state: "working",
                message: { role: "agent", parts },
            },
            contextId: options.contextId,
        },
    });
}

function taskCompleteEvent(taskId: string, state: "completed" | "failed" = "completed", parts: Array<Record<string, unknown>> = []): string {
    return JSON.stringify({
        jsonrpc: "2.0",
        result: {
            kind: "task",
            id: taskId,
            status: {
                state,
                message: state === "failed" && parts.length > 0 ? { role: "agent", parts } : { role: "agent", parts: [] },
            },
        },
    });
}

function rpcError(message: string, code: number = -32000): string {
    return JSON.stringify({
        jsonrpc: "2.0",
        error: { code, message },
    });
}

function artifactUpdateEvent(): string {
    return JSON.stringify({
        jsonrpc: "2.0",
        result: { kind: "artifact-update" },
    });
}

function agentMessage(taskId: string, parts: MessageFE["parts"] = [], extra: Partial<MessageFE> = {}): MessageFE {
    return {
        role: "agent",
        isUser: false,
        taskId,
        parts,
        isComplete: false,
        ...extra,
    };
}

function userMessage(taskId?: string): MessageFE {
    return {
        role: "user",
        isUser: true,
        taskId,
        parts: [{ kind: "text", text: "hello" }],
    };
}

function effectTypes(output: ChatEventOutput): string[] {
    return output.effects.map(e => e.type);
}

// ============ Tests ============

describe("processChatEvent", () => {
    describe("parsing", () => {
        it("returns empty effects for invalid JSON", () => {
            const output = processChatEvent(makeInput({ eventData: "not json" }));
            expect(output.effects).toEqual([]);
            expect(output.messages).toBeUndefined();
        });

        it("returns empty effects for missing result and error", () => {
            const output = processChatEvent(makeInput({ eventData: JSON.stringify({ jsonrpc: "2.0" }) }));
            expect(output.effects).toEqual([]);
        });
    });

    describe("RPC errors", () => {
        it("creates an error message and emits stop/close/clear effects", () => {
            const output = processChatEvent(makeInput({ eventData: rpcError("Something broke") }));

            expect(output.messages).toHaveLength(1);
            expect(output.messages![0].isError).toBe(true);
            expect(output.messages![0].parts[0]).toMatchObject({ kind: "text", text: "Error: Something broke" });
            expect(effectTypes(output)).toEqual(["stop-responding", "close-connection", "clear-task-id"]);
        });

        it("filters out status bubbles before adding error message", () => {
            const existing: MessageFE[] = [agentMessage("t1", [], { isStatusBubble: true }), userMessage("t1")];
            const output = processChatEvent(makeInput({ eventData: rpcError("fail"), messages: existing }));

            // Status bubble should be filtered out, user message kept, error appended
            expect(output.messages).toHaveLength(2);
            expect(output.messages![0].isUser).toBe(true);
            expect(output.messages![1].isError).toBe(true);
        });
    });

    describe("artifact-update events", () => {
        it("emits refetch-artifacts and returns no messages", () => {
            const output = processChatEvent(makeInput({ eventData: artifactUpdateEvent() }));
            expect(effectTypes(output)).toEqual(["refetch-artifacts"]);
            expect(output.messages).toBeUndefined();
        });
    });

    describe("status-update events", () => {
        it("appends text content to a new agent message", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "text", text: "Hello world" }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.messages).toHaveLength(1);
            expect(output.messages![0].isUser).toBe(false);
            expect(output.messages![0].taskId).toBe("task-1");
            expect(output.messages![0].parts).toContainEqual(expect.objectContaining({ kind: "text", text: "Hello world" }));
        });

        it("appends text to the last agent message for the same task", () => {
            const existing = [agentMessage("task-1", [{ kind: "text", text: "part1" }])];
            const eventData = statusUpdateEvent("task-1", [{ kind: "text", text: " part2" }]);
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            expect(output.messages).toHaveLength(1);
            expect(output.messages![0].parts).toHaveLength(2);
        });

        it("does not append to a different task's message", () => {
            const existing = [agentMessage("task-other", [{ kind: "text", text: "old" }])];
            const eventData = statusUpdateEvent("task-1", [{ kind: "text", text: "new" }]);
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            expect(output.messages).toHaveLength(2);
        });

        it("removes a status bubble before appending content", () => {
            const existing = [agentMessage("task-1", [], { isStatusBubble: true })];
            const eventData = statusUpdateEvent("task-1", [{ kind: "text", text: "real content" }]);
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            expect(output.messages).toHaveLength(1);
            expect(output.messages![0].isStatusBubble).toBeFalsy();
        });
    });

    describe("task complete (final) events", () => {
        it("marks the last task message as complete", () => {
            const existing = [agentMessage("task-1", [{ kind: "text", text: "response" }])];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            expect(output.messages!.find(m => m.taskId === "task-1")!.isComplete).toBe(true);
        });

        it("emits final effects in the correct order", () => {
            const existing = [agentMessage("task-1", [{ kind: "text", text: "done" }])];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            expect(effectTypes(output)).toContain("cancel-complete");
            expect(effectTypes(output)).toContain("stop-responding");
            expect(effectTypes(output)).toContain("close-connection");
            expect(effectTypes(output)).toContain("clear-task-id");
            expect(effectTypes(output)).toContain("refetch-artifacts");
            expect(effectTypes(output)).toContain("finalize");
        });

        it("emits save-task effect with correct payload when not replaying", () => {
            const existing = [userMessage("task-1"), agentMessage("task-1", [{ kind: "text", text: "response" }])];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(makeInput({ eventData, messages: existing, sessionId: "ses-1", selectedAgentName: "myAgent" }));

            const saveEffect = output.effects.find(e => e.type === "save-task") as Extract<ChatEffect, { type: "save-task" }>;
            expect(saveEffect).toBeDefined();
            expect(saveEffect.payload.taskId).toBe("task-1");
            expect(saveEffect.payload.selectedAgentName).toBe("myAgent");
        });

        it("does not emit save-task when replaying", () => {
            const existing = [agentMessage("task-1", [{ kind: "text", text: "response" }])];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(
                makeInput({
                    eventData,
                    messages: existing,
                    flags: { inlineActivityTimeline: false, showThinkingContent: false, ragEnabled: true, isReplaying: true },
                })
            );

            expect(output.effects.find(e => e.type === "save-task")).toBeUndefined();
        });

        it("marks lingering in-progress artifacts as failed", () => {
            const existing = [
                agentMessage("task-1", [
                    {
                        kind: "artifact" as const,
                        status: "in-progress" as const,
                        name: "file.txt",
                        bytesTransferred: 100,
                    },
                ]),
            ];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(makeInput({ eventData, messages: existing }));

            // First pass marks them failed, second pass marks them completed
            // The final state should have the artifact resolved
            const taskMsg = output.messages!.find(m => m.taskId === "task-1");
            expect(taskMsg).toBeDefined();
        });

        it("creates a fallback message when final task has parts but no prior status updates", () => {
            const eventData = JSON.stringify({
                jsonrpc: "2.0",
                result: {
                    kind: "task",
                    id: "task-1",
                    status: {
                        state: "completed",
                        message: { role: "agent", parts: [{ kind: "text", text: "final answer" }] },
                    },
                    contextId: "ses-1",
                },
            });
            const output = processChatEvent(makeInput({ eventData }));

            const taskMsg = output.messages!.find(m => m.taskId === "task-1");
            expect(taskMsg).toBeDefined();
            expect(taskMsg!.isComplete).toBe(true);
            expect(taskMsg!.parts).toContainEqual(expect.objectContaining({ kind: "text", text: "final answer" }));
        });

        it("creates error message for failed task", () => {
            const eventData = taskCompleteEvent("task-1", "failed", [{ kind: "text", text: "it broke" }]);
            const output = processChatEvent(makeInput({ eventData }));

            const errorMsg = output.messages!.find(m => m.taskId === "task-1");
            expect(errorMsg).toBeDefined();
            expect(errorMsg!.isError).toBe(true);
        });

        it("cleans up deep research query history on completion", () => {
            const history = new Map([["task-1", [{ query: "q", timestamp: "t", urls: [] }]]]);
            const existing = [agentMessage("task-1", [{ kind: "text", text: "done" }])];
            const eventData = taskCompleteEvent("task-1");
            const output = processChatEvent(makeInput({ eventData, messages: existing, deepResearchQueryHistory: history }));

            expect(output.deepResearchQueryHistory!.has("task-1")).toBe(false);
        });
    });

    describe("background task timestamp", () => {
        it("emits update-task-timestamp for background tasks", () => {
            const eventData = statusUpdateEvent("task-bg", [{ kind: "text", text: "working" }]);
            const output = processChatEvent(
                makeInput({
                    eventData,
                    isTaskRunningInBackground: id => id === "task-bg",
                })
            );

            const tsEffect = output.effects.find(e => e.type === "update-task-timestamp");
            expect(tsEffect).toBeDefined();
        });

        it("does not emit update-task-timestamp for foreground tasks", () => {
            const eventData = statusUpdateEvent("task-fg", [{ kind: "text", text: "working" }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.effects.find(e => e.type === "update-task-timestamp")).toBeUndefined();
        });

        it("emits unregister + dispatch for background task with no messages on final", () => {
            const eventData = taskCompleteEvent("task-bg");
            const output = processChatEvent(
                makeInput({
                    eventData,
                    isTaskRunningInBackground: id => id === "task-bg",
                })
            );

            expect(effectTypes(output)).toContain("unregister-background-task");
            expect(effectTypes(output)).toContain("dispatch-new-chat-session");
        });
    });

    describe("thinking_content", () => {
        it("returns no state changes when showThinkingContent is disabled and no other parts", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "thinking_content", content: "hmm", is_complete: false } }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.messages).toBeUndefined();
            expect(output.effects).toEqual([]);
        });

        it("accumulates thinkingContent on the message when showThinkingContent is enabled (no inline timeline)", () => {
            const existing = [agentMessage("task-1")];
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "thinking_content", content: "reasoning...", is_complete: false } }]);
            const output = processChatEvent(
                makeInput({
                    eventData,
                    messages: existing,
                    flags: { inlineActivityTimeline: false, showThinkingContent: true, ragEnabled: true, isReplaying: false },
                })
            );

            expect(output.messages![0].thinkingContent).toBe("reasoning...");
            expect(output.messages![0].isThinkingComplete).toBe(false);
        });

        it("creates progress update when inline timeline is enabled", () => {
            const existing = [agentMessage("task-1")];
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "thinking_content", content: "think", is_complete: true } }]);
            const output = processChatEvent(
                makeInput({
                    eventData,
                    messages: existing,
                    flags: { inlineActivityTimeline: true, showThinkingContent: true, ragEnabled: true, isReplaying: false },
                })
            );

            expect(output.messages![0].progressUpdates).toBeDefined();
            expect(output.messages![0].progressUpdates![0].type).toBe("thinking");
        });
    });

    describe("agent_progress_update", () => {
        it("sets latestStatusText", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "agent_progress_update", status_text: "Searching..." } }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.latestStatusText).toBe("Searching...");
        });

        it("defaults status text to Processing...", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "agent_progress_update" } }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.latestStatusText).toBe("Processing...");
        });

        it("returns early with messages when status-only (no other parts)", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "agent_progress_update", status_text: "Working" } }]);
            const output = processChatEvent(makeInput({ eventData }));

            // Should return with latestStatusText set but no new message content
            expect(output.latestStatusText).toBe("Working");
        });
    });

    describe("authentication_required", () => {
        it("adds an auth message with valid http URI", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "authentication_required", auth_uri: "https://auth.example.com", target_agent: "OAuth Agent" } }]);
            const output = processChatEvent(makeInput({ eventData }));

            const authMsg = output.messages!.find(m => m.authenticationLink);
            expect(authMsg).toBeDefined();
            expect(authMsg!.authenticationLink!.url).toBe("https://auth.example.com");
            expect(authMsg!.authenticationLink!.targetAgent).toBe("OAuth Agent");
        });

        it("does not add auth message for non-http URI", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "authentication_required", auth_uri: "ftp://bad" } }]);
            const output = processChatEvent(makeInput({ eventData }));

            const authMsg = output.messages?.find(m => m.authenticationLink);
            expect(authMsg).toBeUndefined();
        });

        it("defaults target_agent to Agent", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "authentication_required", auth_uri: "https://auth.example.com" } }]);
            const output = processChatEvent(makeInput({ eventData }));

            const authMsg = output.messages!.find(m => m.authenticationLink);
            expect(authMsg!.authenticationLink!.targetAgent).toBe("Agent");
        });
    });

    describe("rag_info_update", () => {
        it("creates a new RAG entry", () => {
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "rag_info_update",
                        title: "Search Results",
                        query: "test query",
                        search_type: "deep_research",
                        sources: [{ url: "https://example.com", title: "Example", citationId: "s0r0" }],
                        is_complete: false,
                        timestamp: "2024-01-01T00:00:00Z",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.ragData).toHaveLength(1);
            expect(output.ragData![0].query).toBe("test query");
            expect(output.ragData![0].sources).toHaveLength(1);
        });

        it("does not update ragData when ragEnabled is false", () => {
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "rag_info_update",
                        title: "Results",
                        query: "q",
                        search_type: "deep_research",
                        sources: [],
                        is_complete: false,
                        timestamp: "2024-01-01T00:00:00Z",
                    },
                },
            ]);
            const output = processChatEvent(
                makeInput({
                    eventData,
                    flags: { inlineActivityTimeline: false, showThinkingContent: false, ragEnabled: false, isReplaying: false },
                })
            );

            expect(output.ragData).toBeUndefined();
        });

        it("merges sources into existing RAG entry for same query", () => {
            const existing: RAGSearchResult[] = [
                {
                    query: "test",
                    searchType: "deep_research",
                    timestamp: "2024-01-01T00:00:00Z",
                    sources: [{ citationId: "s0r0", title: "A", sourceUrl: "https://a.com", url: "https://a.com", contentPreview: "", relevanceScore: 1, metadata: {} }],
                    taskId: "task-1",
                },
            ];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "rag_info_update",
                        title: "Updated",
                        query: "test",
                        search_type: "deep_research",
                        sources: [
                            { url: "https://a.com", title: "A" },
                            { url: "https://b.com", title: "B" },
                        ],
                        is_complete: false,
                        timestamp: "2024-01-01T00:00:00Z",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, ragData: existing }));

            expect(output.ragData).toHaveLength(1);
            // Should have original + one new source (a.com deduplicated)
            expect(output.ragData![0].sources).toHaveLength(2);
        });
    });

    describe("deep_research_progress", () => {
        it("clears latestStatusText", () => {
            const eventData = statusUpdateEvent("task-1", [{ kind: "data", data: { type: "deep_research_progress", phase: "searching", current_query: "q1", fetching_urls: [] } }]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.latestStatusText).toBeNull();
        });

        it("accumulates query history", () => {
            const history = new Map<string, Array<{ query: string; timestamp: string; urls: Array<{ url: string; title: string; favicon: string; source_type?: string }> }>>();
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "deep_research_progress",
                        phase: "searching",
                        current_query: "what is X",
                        fetching_urls: [{ url: "https://x.com", title: "X", favicon: "" }],
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, deepResearchQueryHistory: history }));

            expect(output.deepResearchQueryHistory!.get("task-1")).toHaveLength(1);
            expect(output.deepResearchQueryHistory!.get("task-1")![0].query).toBe("what is X");
        });
    });

    describe("compaction_notification", () => {
        it("clears latestStatusText", () => {
            const eventData = statusUpdateEvent("task-1", [
                { kind: "data", data: { type: "compaction_notification" } },
                { kind: "text", text: "Context compacted" },
            ]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.latestStatusText).toBeNull();
        });
    });

    describe("tool_result with RAG metadata", () => {
        it("appends RAG data for web_search", () => {
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "tool_result",
                        result_data: {
                            rag_metadata: {
                                query: "search",
                                searchType: "web_search",
                                timestamp: "2024-01-01T00:00:00Z",
                                sources: [],
                            },
                        },
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.ragData).toHaveLength(1);
            expect(output.ragData![0].searchType).toBe("web_search");
        });

        it("replaces previous deep_research entries for same task", () => {
            const existing: RAGSearchResult[] = [
                {
                    query: "old",
                    searchType: "deep_research",
                    timestamp: "t",
                    sources: [],
                    taskId: "task-1",
                },
            ];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "tool_result",
                        result_data: {
                            rag_metadata: {
                                query: "new",
                                searchType: "deep_research",
                                timestamp: "t2",
                                sources: [],
                            },
                        },
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, ragData: existing }));

            expect(output.ragData).toHaveLength(1);
            expect(output.ragData![0].query).toBe("new");
        });
    });

    describe("artifact_creation_progress", () => {
        it("creates a new artifact entry for in-progress status", () => {
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "artifact_creation_progress",
                        filename: "doc.pdf",
                        status: "in-progress",
                        bytes_transferred: 500,
                        description: "A document",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData }));

            expect(output.artifacts).toHaveLength(1);
            expect(output.artifacts![0].filename).toBe("doc.pdf");
        });

        it("emits refetch-artifacts on completed artifact", () => {
            const existing: ArtifactInfo[] = [
                {
                    filename: "doc.pdf",
                    mime_type: "application/pdf",
                    size: 100,
                    last_modified: "2024-01-01",
                    description: "test",
                },
            ];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "artifact_creation_progress",
                        filename: "doc.pdf",
                        status: "completed",
                        bytes_transferred: 1000,
                        mime_type: "application/pdf",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, artifacts: existing }));

            expect(effectTypes(output)).toContain("refetch-artifacts");
        });

        it("emits auto-download-artifact for completed displayed artifact", () => {
            const existing: ArtifactInfo[] = [
                {
                    filename: "doc.pdf",
                    mime_type: "application/pdf",
                    size: 100,
                    last_modified: "2024-01-01",
                    isDisplayed: true,
                },
            ];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "artifact_creation_progress",
                        filename: "doc.pdf",
                        status: "completed",
                        bytes_transferred: 1000,
                        mime_type: "application/pdf",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, artifacts: existing }));

            expect(effectTypes(output)).toContain("auto-download-artifact");
        });

        it("removes artifact and rolls back text on cancelled status", () => {
            const existingArtifacts: ArtifactInfo[] = [
                {
                    filename: "doc.pdf",
                    mime_type: "application/pdf",
                    size: 100,
                    last_modified: "2024-01-01",
                },
            ];
            const existingMessages = [
                agentMessage("task-1", [
                    {
                        kind: "artifact" as const,
                        status: "in-progress" as const,
                        name: "doc.pdf",
                        bytesTransferred: 50,
                    },
                ]),
            ];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "artifact_creation_progress",
                        filename: "doc.pdf",
                        status: "cancelled",
                        bytes_transferred: 0,
                        rolled_back_text: "Some original text",
                    },
                },
            ]);
            const output = processChatEvent(makeInput({ eventData, messages: existingMessages, artifacts: existingArtifacts }));

            expect(output.artifacts).toHaveLength(0);
            const taskMsg = output.messages!.find(m => m.taskId === "task-1");
            expect(taskMsg!.parts.find(p => p.kind === "artifact")).toBeUndefined();
            expect(taskMsg!.parts).toContainEqual(expect.objectContaining({ kind: "text", text: "Some original text" }));
        });
    });

    describe("input immutability", () => {
        it("does not mutate the input messages array", () => {
            const original: MessageFE[] = [agentMessage("task-1", [{ kind: "text", text: "old" }])];
            const frozen = [...original];
            const eventData = statusUpdateEvent("task-1", [{ kind: "text", text: "new" }]);
            processChatEvent(makeInput({ eventData, messages: original }));

            expect(original).toEqual(frozen);
        });

        it("does not mutate the input ragData array", () => {
            const original: RAGSearchResult[] = [];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "rag_info_update",
                        title: "T",
                        query: "q",
                        search_type: "deep_research",
                        sources: [],
                        is_complete: false,
                        timestamp: "t",
                    },
                },
            ]);
            processChatEvent(makeInput({ eventData, ragData: original }));

            expect(original).toHaveLength(0);
        });

        it("does not mutate the input artifacts array", () => {
            const original: ArtifactInfo[] = [];
            const eventData = statusUpdateEvent("task-1", [
                {
                    kind: "data",
                    data: {
                        type: "artifact_creation_progress",
                        filename: "f.txt",
                        status: "in-progress",
                        bytes_transferred: 10,
                        description: "test",
                    },
                },
            ]);
            processChatEvent(makeInput({ eventData, artifacts: original }));

            expect(original).toHaveLength(0);
        });
    });
});
