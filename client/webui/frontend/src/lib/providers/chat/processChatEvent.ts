import { v4 as uuidv4 } from "uuid";

import { filterRenderableDataParts, checkHasVisibleContent, isCompactionNotificationBubble } from "@/lib/utils/messageProcessing";

import type { DataPart, FileAttachment, SendStreamingMessageSuccessResponse, JSONRPCErrorResponse, TaskStatusUpdateEvent, ArtifactPart, PartFE, MessageFE, RAGSearchResult, ProgressUpdate, ArtifactInfo, Part } from "@/lib/types";

// Force uuid to use crypto.getRandomValues() fallback for non-secure (HTTP) contexts
const v4 = () => uuidv4({});

// ============ Data Part Payloads ============

interface ThinkingContentPayload {
    type: "thinking_content";
    content: string;
    is_complete: boolean;
}

interface AgentProgressUpdatePayload {
    type: "agent_progress_update";
    status_text?: string;
}

interface ArtifactCreationProgressPayload {
    type: "artifact_creation_progress";
    filename: string;
    status: "in-progress" | "completed" | "failed" | "cancelled";
    bytes_transferred: number;
    mime_type?: string;
    description?: string;
    artifact_chunk?: string;
    version?: number;
    rolled_back_text?: string;
    tags?: string[];
}

interface AuthenticationRequiredPayload {
    type: "authentication_required";
    auth_uri?: string;
    target_agent?: string;
    gateway_task_id?: string;
}

interface RagInfoUpdatePayload {
    type: "rag_info_update";
    title: string;
    query: string;
    search_type: string;
    search_turn?: number;
    sources: Array<{
        url: string;
        title: string;
        favicon?: string;
        source_type?: string;
        citationId?: string;
    }>;
    is_complete: boolean;
    timestamp: string;
}

interface DeepResearchProgressPayload {
    type: "deep_research_progress";
    phase: string;
    current_query: string;
    fetching_urls: Array<{ url: string; title: string; favicon: string; source_type?: string }>;
}

interface CompactionNotificationPayload {
    type: "compaction_notification";
}

interface ToolResultPayload {
    type: "tool_result";
    result_data?: {
        rag_metadata?: {
            query: string;
            title?: string;
            searchType: RAGSearchResult["searchType"];
            timestamp: string;
            sources: RAGSearchResult["sources"];
            metadata?: RAGSearchResult["metadata"];
        };
        [key: string]: unknown;
    };
    [key: string]: unknown;
}

interface ToolInvocationStartPayload {
    type: "tool_invocation_start";
}

type ChatDataPartPayload =
    | ThinkingContentPayload
    | AgentProgressUpdatePayload
    | ArtifactCreationProgressPayload
    | AuthenticationRequiredPayload
    | RagInfoUpdatePayload
    | DeepResearchProgressPayload
    | CompactionNotificationPayload
    | ToolResultPayload
    | ToolInvocationStartPayload;

function asTypedPayload(data: unknown): ChatDataPartPayload | null {
    if (typeof data !== "object" || data === null || !("type" in data)) return null;
    return typeof (data as Record<string, unknown>).type === "string" ? (data as ChatDataPartPayload) : null;
}

// ============ Types ============

export interface QueryHistoryEntry {
    query: string;
    timestamp: string;
    // source_type matches the backend wire format and InlineResearchProgress component interface
    urls: Array<{ url: string; title: string; favicon: string; source_type?: string }>;
}

/** Everything the reducer needs to compute the next state. */
export interface ChatEventInput {
    eventData: string;
    messages: MessageFE[];
    ragData: RAGSearchResult[];
    artifacts: ArtifactInfo[];
    flags: {
        inlineActivityTimeline: boolean;
        showThinkingContent: boolean;
        ragEnabled: boolean;
        isReplaying: boolean;
    };
    sessionId: string;
    selectedAgentName: string;
    deepResearchQueryHistory: Map<string, QueryHistoryEntry[]>;
    /** Monotonically increasing — caller bumps before each call. */
    eventSequence: number;
    /** Check whether a given task ID is running in the background. */
    isTaskRunningInBackground: (taskId: string) => boolean;
}

/** State patches returned by the reducer. Only defined keys should be applied. */
export interface ChatEventOutput {
    messages?: MessageFE[];
    ragData?: RAGSearchResult[];
    artifacts?: ArtifactInfo[];
    latestStatusText?: string | null;
    deepResearchQueryHistory?: Map<string, QueryHistoryEntry[]>;
    effects: ChatEffect[];
}

export type ChatEffect =
    | { type: "close-connection" }
    | { type: "stop-responding" }
    | { type: "clear-task-id" }
    | { type: "cancel-complete" }
    | { type: "refetch-artifacts" }
    | {
          type: "save-task";
          payload: {
              taskId: string;
              messages: MessageFE[];
              sessionId: string;
              selectedAgentName: string;
              ragData: RAGSearchResult[];
          };
      }
    | { type: "unregister-background-task"; payload: { taskId: string } }
    | { type: "update-task-timestamp"; payload: { taskId: string; timestamp: number } }
    | { type: "auto-download-artifact"; payload: { filename: string } }
    | { type: "dispatch-new-chat-session" }
    | { type: "finalize" };

// ============ Processor ============

/**
 * Processes a single chat SSE event against the current state and returns
 * state updates plus a list of side-effect descriptors.
 *
 * I/O side effects are deferred via ChatEffect descriptors.
 */
export function processChatEvent(input: ChatEventInput): ChatEventOutput {
    const { eventData, flags, sessionId, eventSequence, isTaskRunningInBackground } = input;
    // Clone the Map (and its value arrays) to avoid mutating the caller's data
    const deepResearchQueryHistory = new Map([...input.deepResearchQueryHistory].map(([k, v]) => [k, [...v]]));
    let messages = [...input.messages];
    let ragData: RAGSearchResult[] | undefined;
    let artifacts: ArtifactInfo[] | undefined;
    let latestStatusText: string | null | undefined;
    const effects: ChatEffect[] = [];

    // Builds the full output from all accumulated state. Used by early returns
    // and the normal exit to avoid accidentally dropping state.
    const buildOutput = (): ChatEventOutput => {
        const output: ChatEventOutput = { messages, effects };
        if (ragData !== undefined) output.ragData = ragData;
        if (artifacts !== undefined) output.artifacts = artifacts;
        if (latestStatusText !== undefined) output.latestStatusText = latestStatusText;
        output.deepResearchQueryHistory = deepResearchQueryHistory;
        return output;
    };

    // --- Parse ---
    let rpcResponse: SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;
    try {
        rpcResponse = JSON.parse(eventData) as SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;
    } catch {
        console.error("Failed to parse SSE message");
        return { effects: [] };
    }

    // --- Background task timestamp ---
    if ("result" in rpcResponse && rpcResponse.result) {
        const result = rpcResponse.result;
        let taskIdFromResult: string | undefined;
        if (result.kind === "task") taskIdFromResult = result.id;
        else if (result.kind === "status-update") taskIdFromResult = result.taskId;
        if (taskIdFromResult && isTaskRunningInBackground(taskIdFromResult)) {
            effects.push({ type: "update-task-timestamp", payload: { taskId: taskIdFromResult, timestamp: Date.now() } });
        }
    }

    // --- RPC Error ---
    if ("error" in rpcResponse && rpcResponse.error) {
        const errorContent = rpcResponse.error;
        const messageContent = `Error: ${errorContent.message}`;

        const newMessages = messages.filter(msg => !msg.isStatusBubble);
        newMessages.push({
            role: "agent",
            parts: [{ kind: "text", text: messageContent }],
            isUser: false,
            isError: true,
            isComplete: true,
            metadata: {
                messageId: `msg-${v4()}`,
                lastProcessedEventSequence: eventSequence,
            },
        });

        effects.push({ type: "stop-responding" }, { type: "close-connection" }, { type: "clear-task-id" });
        return { messages: newMessages, effects };
    }

    if (!("result" in rpcResponse) || !rpcResponse.result) {
        console.warn("Received SSE message without a result or error field.", rpcResponse);
        return { effects: [] };
    }

    const result = rpcResponse.result;
    let isFinalEvent = false;
    let messageToProcess: { parts: Part[] } | undefined;
    let currentTaskIdFromResult: string | undefined;

    // --- Determine event type ---
    switch (result.kind) {
        case "task":
            isFinalEvent = true;
            if (result.status?.state === "failed" && result.status?.message) {
                messageToProcess = result.status.message;
            } else {
                messageToProcess = undefined;
            }
            currentTaskIdFromResult = result.id;
            break;
        case "status-update":
            isFinalEvent = result.final;
            messageToProcess = result.status?.message;
            currentTaskIdFromResult = result.taskId;
            break;
        case "artifact-update":
            effects.push({ type: "refetch-artifacts" });
            return { effects };
        default:
            console.warn("Received unknown result kind in SSE message:", result);
            return { effects };
    }

    // --- Process data parts ---
    if (messageToProcess?.parts) {
        const dataParts = messageToProcess.parts.filter(p => p.kind === "data") as DataPart[];
        if (dataParts.length > 0) {
            for (const part of dataParts) {
                const data = asTypedPayload(part.data);
                if (data) {
                    switch (data.type) {
                        case "thinking_content": {
                            if (!flags.showThinkingContent) {
                                const otherPartsThinking = messageToProcess.parts.filter(p => p.kind !== "data");
                                if (otherPartsThinking.length === 0) {
                                    return { effects };
                                }
                                break;
                            }

                            const { content: thinkingText, is_complete: isThinkingComplete } = data;

                            const thinkingUpdate: ProgressUpdate = {
                                type: "thinking" as const,
                                text: "Thinking",
                                timestamp: Date.now(),
                                expandableContent: thinkingText,
                                isExpandableComplete: isThinkingComplete,
                            };

                            if (flags.inlineActivityTimeline) {
                                messages = appendProgressUpdate(messages, currentTaskIdFromResult, eventSequence, thinkingUpdate, undefined, {
                                    progressUpdater: existing => {
                                        const updates = [...existing];
                                        const lastThinkingIdx = updates.findLastIndex(p => p.type === "thinking");
                                        const lastThinkingEntry = lastThinkingIdx >= 0 ? updates[lastThinkingIdx] : null;

                                        if (lastThinkingEntry && !lastThinkingEntry.isExpandableComplete) {
                                            updates[lastThinkingIdx] = {
                                                ...lastThinkingEntry,
                                                expandableContent: (lastThinkingEntry.expandableContent || "") + thinkingText,
                                                isExpandableComplete: isThinkingComplete,
                                            };
                                        } else {
                                            updates.push(thinkingUpdate);
                                        }
                                        return updates;
                                    },
                                    messageUpdater: msg => ({
                                        thinkingContent: (msg.thinkingContent || "") + thinkingText,
                                        isThinkingComplete: isThinkingComplete,
                                    }),
                                });
                            } else {
                                const lastMsg = messages[messages.length - 1];
                                if (lastMsg && !lastMsg.isUser && lastMsg.taskId === currentTaskIdFromResult) {
                                    messages[messages.length - 1] = {
                                        ...lastMsg,
                                        thinkingContent: (lastMsg.thinkingContent || "") + thinkingText,
                                        isThinkingComplete: isThinkingComplete,
                                    };
                                }
                            }

                            const otherPartsThinking = messageToProcess.parts.filter(p => p.kind !== "data");
                            if (otherPartsThinking.length === 0) {
                                break;
                            }
                            break;
                        }
                        case "agent_progress_update": {
                            const statusText = String(data?.status_text ?? "Processing...");
                            latestStatusText = statusText;

                            if (flags.inlineActivityTimeline) {
                                const progressUpdate: ProgressUpdate = {
                                    type: "status",
                                    text: statusText,
                                    timestamp: Date.now(),
                                };

                                messages = appendProgressUpdate(
                                    messages,
                                    currentTaskIdFromResult,
                                    eventSequence,
                                    progressUpdate,
                                    { isStatusBubble: false },
                                    {
                                        progressUpdater: existing => {
                                            const updates = [...existing];
                                            const lastThinkingIdx = updates.findLastIndex((p: ProgressUpdate) => p.type === "thinking");
                                            if (lastThinkingIdx >= 0 && !updates[lastThinkingIdx].isExpandableComplete) {
                                                updates[lastThinkingIdx] = {
                                                    ...updates[lastThinkingIdx],
                                                    isExpandableComplete: true,
                                                };
                                            }
                                            updates.push(progressUpdate);
                                            return updates;
                                        },
                                        messageUpdater: msg => {
                                            const updates = msg.progressUpdates || [];
                                            const lastThinkingIdx = updates.findLastIndex((p: ProgressUpdate) => p.type === "thinking");
                                            const needsClose = lastThinkingIdx >= 0 && !updates[lastThinkingIdx].isExpandableComplete;
                                            return needsClose ? { isThinkingComplete: true } : {};
                                        },
                                    }
                                );
                            }

                            const otherParts = messageToProcess.parts.filter(p => p.kind !== "data");
                            if (otherParts.length === 0) {
                                return buildOutput();
                            }
                            break;
                        }
                        case "artifact_creation_progress": {
                            const result = processArtifactCreationProgress(data, messages, artifacts ?? input.artifacts, currentTaskIdFromResult, eventSequence, sessionId);
                            messages = result.messages;
                            artifacts = result.artifacts;
                            effects.push(...result.effects);
                            return buildOutput();
                        }
                        case "tool_invocation_start":
                            break;
                        case "authentication_required": {
                            const auth_uri = data?.auth_uri;
                            const target_agent = typeof data?.target_agent === "string" ? data.target_agent : "Agent";
                            const gateway_task_id = typeof data?.gateway_task_id === "string" ? data.gateway_task_id : undefined;
                            if (typeof auth_uri === "string" && auth_uri.startsWith("http")) {
                                const authMessage: MessageFE = {
                                    role: "agent",
                                    parts: [{ kind: "text", text: "" }],
                                    authenticationLink: {
                                        url: auth_uri,
                                        text: "Click to Authenticate",
                                        targetAgent: target_agent,
                                        gatewayTaskId: gateway_task_id,
                                    },
                                    isUser: false,
                                    isComplete: true,
                                    metadata: { messageId: `auth-${v4()}` },
                                };
                                messages = [...messages, authMessage];
                            }
                            break;
                        }
                        case "rag_info_update": {
                            if (flags.ragEnabled) {
                                ragData = processRagInfoUpdate(data, ragData ?? input.ragData, currentTaskIdFromResult);
                            }
                            break;
                        }
                        case "deep_research_progress": {
                            latestStatusText = null;
                            const queryHistory = processDeepResearchProgress(data, deepResearchQueryHistory, currentTaskIdFromResult);
                            // MUTATION: InlineResearchProgress reads query_history directly from
                            // the DataPart.data object reference in the message parts array.
                            // Removing this requires changing the component to receive query
                            // history via a separate prop or context.
                            if (queryHistory) {
                                (data as DeepResearchProgressPayload & Record<string, unknown>).query_history = queryHistory;
                            }
                            break;
                        }
                        case "compaction_notification": {
                            latestStatusText = null;
                            break;
                        }
                        case "tool_result": {
                            if (flags.ragEnabled) {
                                ragData = processToolResultRag(data, ragData ?? input.ragData, currentTaskIdFromResult);
                            }
                            break;
                        }
                        default:
                            console.log("Received unknown data part type:", (data as { type: string }).type);
                    }
                }
            }
        }
    }

    // --- Filter renderable parts ---
    const hasDeepResearchProgress = messageToProcess?.parts?.some(p => {
        if (p.kind === "data") {
            const dataPart = p as DataPart;
            return dataPart.data && dataPart.data.type === "deep_research_progress";
        }
        return false;
    });

    const newContentParts = filterRenderableDataParts(messageToProcess?.parts || [], !!hasDeepResearchProgress);
    const hasNewFiles = newContentParts.some(p => p.kind === "file");
    const isTaskFailed = result.kind === "task" && result.status?.state === "failed";

    // --- Update messages with content ---
    const responseMessageId = rpcResponse.id?.toString() ?? `msg-${v4()}`;
    const responseContextId = "result" in rpcResponse && rpcResponse.result && "contextId" in rpcResponse.result ? (rpcResponse.result as unknown as { contextId?: string }).contextId : undefined;

    messages = applyContentToMessages(messages, newContentParts, {
        hasNewFiles,
        isFinalEvent,
        isTaskFailed,
        taskId: currentTaskIdFromResult,
        eventSequence,
        messageId: responseMessageId,
        contextId: responseContextId,
        fallbackSessionId: sessionId,
    });

    // --- Final event handling ---
    if (isFinalEvent) {
        latestStatusText = null;

        // Finalize in-progress artifacts for THIS task — mark as failed since
        // the artifact_completed signal should have arrived before the final event.
        for (let i = messages.length - 1; i >= 0; i--) {
            const msg = messages[i];
            if (msg.taskId === currentTaskIdFromResult && msg.parts.some(p => p.kind === "artifact" && (p as ArtifactPart).status === "in-progress")) {
                const finalParts: PartFE[] = msg.parts.map(p => {
                    if (p.kind === "artifact" && (p as ArtifactPart).status === "in-progress") {
                        return { ...p, status: "failed", error: `Artifact creation for "${(p as ArtifactPart).name}" did not complete.` } as ArtifactPart;
                    }
                    return p;
                });
                messages[i] = { ...msg, parts: finalParts, isError: true, isComplete: true };
            }
        }

        // Mark last task message as complete
        const taskMessageIndex = messages.findLastIndex(msg => !msg.isUser && msg.taskId === currentTaskIdFromResult);
        if (taskMessageIndex !== -1) {
            messages[taskMessageIndex] = {
                ...messages[taskMessageIndex],
                isComplete: true,
                metadata: { ...messages[taskMessageIndex].metadata, lastProcessedEventSequence: eventSequence },
            };
        } else if (result.kind === "task" && result.status?.state !== "failed" && result.status?.message?.parts) {
            const fallbackParts = (result.status.message.parts as PartFE[]).filter((p: PartFE) => p.kind === "text" || p.kind === "file");
            if (fallbackParts.length > 0) {
                messages.push({
                    role: "agent",
                    parts: fallbackParts,
                    taskId: currentTaskIdFromResult,
                    isUser: false,
                    isComplete: true,
                    metadata: {
                        messageId: rpcResponse.id?.toString() || `msg-${v4()}`,
                        sessionId: (result as unknown as { contextId?: string }).contextId || sessionId,
                        lastProcessedEventSequence: eventSequence,
                    },
                });
            }
        }

        // Save task (unless replaying)
        if (currentTaskIdFromResult && !flags.isReplaying) {
            const taskMessagesToSave = messages.filter(msg => msg.taskId === currentTaskIdFromResult && !msg.isStatusBubble);
            if (taskMessagesToSave.length > 0) {
                const taskSessionId = (result as TaskStatusUpdateEvent).contextId || sessionId;
                // Snapshot RAG data now so the effect handler doesn't read a stale ref
                const currentRagData = ragData ?? input.ragData;
                const taskRagSnapshot = currentRagData.filter(r => r.taskId === currentTaskIdFromResult);
                effects.push({
                    type: "save-task",
                    payload: {
                        taskId: currentTaskIdFromResult,
                        messages: taskMessagesToSave,
                        sessionId: taskSessionId,
                        selectedAgentName: input.selectedAgentName,
                        ragData: taskRagSnapshot,
                    },
                });
            } else if (isTaskRunningInBackground(currentTaskIdFromResult)) {
                effects.push({ type: "unregister-background-task", payload: { taskId: currentTaskIdFromResult } }, { type: "dispatch-new-chat-session" });
            }
        }

        // Cleanup sweep: mark any remaining in-progress artifacts across ALL messages
        // as completed (e.g. artifacts from other tasks that weren't finalized).
        messages = messages.map(msg => {
            if (msg.isUser) return msg;
            const hasInProgressArtifacts = msg.parts.some(p => p.kind === "artifact" && (p as ArtifactPart).status === "in-progress");
            if (!hasInProgressArtifacts) return msg;

            return {
                ...msg,
                parts: msg.parts.map(part => {
                    if (part.kind === "artifact" && (part as ArtifactPart).status === "in-progress") {
                        const artifactPart = part as ArtifactPart;
                        const fileAttachment: FileAttachment = {
                            name: artifactPart.name,
                            mime_type: artifactPart.file?.mime_type,
                            uri: `artifact://${sessionId}/${artifactPart.name}`,
                        };
                        return {
                            kind: "artifact" as const,
                            status: "completed" as const,
                            name: artifactPart.name,
                            file: fileAttachment,
                        };
                    }
                    return part;
                }),
            };
        });

        effects.push({ type: "cancel-complete" }, { type: "stop-responding" }, { type: "close-connection" }, { type: "clear-task-id" }, { type: "refetch-artifacts" }, { type: "finalize" });

        // Clean up query history for completed task
        if (currentTaskIdFromResult) {
            deepResearchQueryHistory.delete(currentTaskIdFromResult);
        }
    }

    return buildOutput();
}

// ============ Helpers ============

/** Find-or-create the last AI message for a task and apply a progress update. Returns a new messages array. */
function appendProgressUpdate(
    messages: MessageFE[],
    taskId: string | undefined,
    eventSequence: number,
    update: ProgressUpdate,
    extraFields?: Partial<MessageFE>,
    options?: {
        progressUpdater?: (existing: ProgressUpdate[]) => ProgressUpdate[];
        messageUpdater?: (msg: MessageFE) => Partial<MessageFE>;
    }
): MessageFE[] {
    const result = [...messages];
    const lastMsg = result[result.length - 1];
    if (lastMsg && !lastMsg.isUser && lastMsg.taskId === taskId) {
        const updatedProgressUpdates = options?.progressUpdater ? options.progressUpdater(lastMsg.progressUpdates || []) : [...(lastMsg.progressUpdates || []), update];
        const msgExtra = options?.messageUpdater ? options.messageUpdater(lastMsg) : {};
        result[result.length - 1] = {
            ...lastMsg,
            progressUpdates: updatedProgressUpdates,
            ...msgExtra,
            ...extraFields,
        };
    } else {
        result.push({
            role: "agent",
            parts: [],
            taskId,
            isUser: false,
            isComplete: false,
            progressUpdates: [update],
            metadata: {
                messageId: `msg-${v4()}`,
                lastProcessedEventSequence: eventSequence,
            },
            ...extraFields,
        });
    }
    return result;
}

// ============ Sub-processors ============

function processArtifactCreationProgress(
    data: ArtifactCreationProgressPayload,
    inputMessages: MessageFE[],
    inputArtifacts: ArtifactInfo[],
    currentTaskIdFromResult: string | undefined,
    eventSequence: number,
    sessionId: string
): { messages: MessageFE[]; artifacts: ArtifactInfo[]; effects: ChatEffect[] } {
    const { filename, status, bytes_transferred, mime_type, description, artifact_chunk, version, rolled_back_text, tags } = data;

    let messages = [...inputMessages];
    let artifactsList = [...inputArtifacts];
    const effects: ChatEffect[] = [];

    // Handle "cancelled" status — only update the last agent message for this task,
    // matching the original behavior to avoid removing legitimate earlier artifact references.
    if (status === "cancelled") {
        const lastAgentIdx = messages.findLastIndex(m => !m.isUser && m.taskId === currentTaskIdFromResult);
        if (lastAgentIdx !== -1) {
            const agentMsg = messages[lastAgentIdx];
            let parts = agentMsg.parts.filter(p => !(p.kind === "artifact" && (p as ArtifactPart).name === filename));
            if (rolled_back_text) {
                parts = [...parts, { kind: "text" as const, text: rolled_back_text }];
            }
            messages = [...messages];
            messages[lastAgentIdx] = { ...agentMsg, parts };
        }
        artifactsList = artifactsList.filter(a => a.filename !== filename);
        return { messages, artifacts: artifactsList, effects };
    }

    // Track if we need to trigger auto-download
    let shouldAutoDownload = false;

    // Update artifacts list
    const existingIndex = artifactsList.findIndex(a => a.filename === filename);
    if (existingIndex >= 0) {
        const existingArtifact = artifactsList[existingIndex];
        const isDisplayed = existingArtifact.isDisplayed ?? false;

        if (status === "completed" && isDisplayed) {
            shouldAutoDownload = true;
        }

        artifactsList = [...artifactsList];
        let accumulatedContent: string | undefined;
        if (status === "in-progress" && artifact_chunk) {
            accumulatedContent = (existingArtifact.accumulatedContent || "") + artifact_chunk;
        } else if (status === "completed" && !isDisplayed) {
            accumulatedContent = undefined;
        } else {
            accumulatedContent = existingArtifact.accumulatedContent;
        }

        artifactsList[existingIndex] = {
            ...existingArtifact,
            description: description !== undefined ? description : existingArtifact.description,
            size: bytes_transferred || existingArtifact.size,
            last_modified: new Date().toISOString(),
            uri: existingArtifact.uri || `artifact://${sessionId}/${filename}`,
            accumulatedContent,
            isAccumulatedContentPlainText: status === "in-progress" && artifact_chunk ? true : existingArtifact.isAccumulatedContentPlainText,
            mime_type: status === "completed" && mime_type ? mime_type : existingArtifact.mime_type,
            needsEmbedResolution: status === "completed" ? true : existingArtifact.needsEmbedResolution,
            tags: tags !== undefined ? tags : existingArtifact.tags,
        };
    } else if (description !== undefined || status === "in-progress") {
        artifactsList = [
            ...artifactsList,
            {
                filename,
                description: description ?? null,
                mime_type: mime_type ?? "application/octet-stream",
                size: bytes_transferred ?? 0,
                last_modified: new Date().toISOString(),
                uri: `artifact://${sessionId}/${filename}`,
                accumulatedContent: status === "in-progress" && artifact_chunk ? artifact_chunk : undefined,
                isAccumulatedContentPlainText: status === "in-progress" && artifact_chunk ? true : false,
                needsEmbedResolution: status === "completed" ? true : false,
                tags,
            },
        ];
    }

    if (shouldAutoDownload) {
        effects.push({ type: "auto-download-artifact", payload: { filename } });
    }

    // Update messages with artifact part
    let agentMessageIndex = messages.findLastIndex(m => !m.isUser && m.taskId === currentTaskIdFromResult);

    if (agentMessageIndex === -1) {
        const newAgentMessage: MessageFE = {
            role: "agent",
            parts: [],
            taskId: currentTaskIdFromResult,
            isUser: false,
            isComplete: false,
            isStatusBubble: false,
            metadata: { lastProcessedEventSequence: eventSequence },
        };
        messages = [...messages, newAgentMessage];
        agentMessageIndex = messages.length - 1;
    }

    const agentMessage = { ...messages[agentMessageIndex], parts: [...messages[agentMessageIndex].parts] };
    agentMessage.isStatusBubble = false;
    const artifactPartIndex = agentMessage.parts.findIndex(p => p.kind === "artifact" && (p as ArtifactPart).name === filename);

    if (status === "in-progress") {
        if (artifactPartIndex > -1) {
            const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
            agentMessage.parts[artifactPartIndex] = { ...existingPart, bytesTransferred: bytes_transferred, status: "in-progress" };
        } else {
            agentMessage.parts.push({
                kind: "artifact",
                status: "in-progress",
                name: filename,
                bytesTransferred: bytes_transferred,
            });
        }
    } else if (status === "completed") {
        const fileAttachment: FileAttachment = {
            name: filename,
            mime_type,
            uri: version !== undefined ? `artifact://${sessionId}/${filename}?version=${version}` : `artifact://${sessionId}/${filename}`,
        };
        if (artifactPartIndex > -1) {
            const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
            const updatedPart: ArtifactPart = { ...existingPart, status: "completed", file: fileAttachment };
            delete updatedPart.bytesTransferred;
            agentMessage.parts[artifactPartIndex] = updatedPart;
        } else {
            agentMessage.parts.push({
                kind: "artifact",
                status: "completed",
                name: filename,
                file: fileAttachment,
            });
        }
        effects.push({ type: "refetch-artifacts" });
    } else {
        // status === "failed"
        const errorMsg = `Failed to create artifact: ${filename}`;
        if (artifactPartIndex > -1) {
            const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
            const updatedPart: ArtifactPart = { ...existingPart, status: "failed", error: errorMsg };
            delete updatedPart.bytesTransferred;
            agentMessage.parts[artifactPartIndex] = updatedPart;
        } else {
            agentMessage.parts.push({
                kind: "artifact",
                status: "failed",
                name: filename,
                error: errorMsg,
            });
        }
        agentMessage.isError = true;
    }

    messages[agentMessageIndex] = agentMessage;
    messages = messages.filter(m => !m.isStatusBubble || m.parts.some(p => p.kind === "artifact" || p.kind === "file"));

    return { messages, artifacts: artifactsList, effects };
}

function processRagInfoUpdate(data: RagInfoUpdatePayload, prevRagData: RAGSearchResult[], currentTaskIdFromResult: string | undefined): RAGSearchResult[] {
    const ragData = [...prevRagData];
    const searchTurn = data.search_turn ?? ragData.filter(r => r.taskId === currentTaskIdFromResult).length;

    const formattedSources = (data.sources || []).map((source, idx) => ({
        citationId: source.citationId || `s${searchTurn}r${idx}`,
        title: source.title || source.url,
        sourceUrl: source.url,
        url: source.url,
        contentPreview: `Source: ${source.title || source.url}`,
        relevanceScore: 1.0,
        retrievedAt: data.timestamp,
        metadata: {
            favicon: source.favicon || `https://www.google.com/s2/favicons?domain=${source.url}&sz=32`,
            type: "web_search",
            sourceType: source.source_type || "web",
        },
    }));

    const existingIndex = ragData.findIndex(r => r.searchType === "deep_research" && r.taskId === currentTaskIdFromResult && r.query === data.query);

    if (existingIndex !== -1) {
        const existing = ragData[existingIndex];
        const existingUrls = new Set(existing.sources.map(s => s.sourceUrl || s.url));
        const newSources = formattedSources.filter(s => !existingUrls.has(s.sourceUrl || s.url));
        ragData[existingIndex] = {
            ...existing,
            title: data.title || existing.title,
            sources: [...existing.sources, ...newSources],
        };
    } else {
        ragData.push({
            query: data.query,
            title: data.title,
            searchType: "deep_research" as const,
            timestamp: data.timestamp,
            sources: formattedSources,
            taskId: currentTaskIdFromResult,
        });
    }

    return ragData;
}

function processDeepResearchProgress(data: DeepResearchProgressPayload, deepResearchQueryHistory: Map<string, QueryHistoryEntry[]>, currentTaskIdFromResult: string | undefined): QueryHistoryEntry[] | null {
    if (!currentTaskIdFromResult) return null;

    const taskHistory = deepResearchQueryHistory.get(currentTaskIdFromResult) || [];

    if (data.current_query) {
        const existingQueryIndex = taskHistory.findIndex(q => q.query === data.current_query);
        if (existingQueryIndex === -1) {
            taskHistory.push({
                query: data.current_query,
                timestamp: new Date().toISOString(),
                urls: data.fetching_urls || [],
            });
        } else if (data.fetching_urls && data.fetching_urls.length > 0) {
            const existingEntry = taskHistory[existingQueryIndex];
            const existingUrls = new Set(existingEntry.urls.map(u => u.url));
            const newUrls = data.fetching_urls.filter(u => !existingUrls.has(u.url));
            if (newUrls.length > 0) {
                taskHistory[existingQueryIndex] = {
                    ...existingEntry,
                    urls: [...existingEntry.urls, ...newUrls],
                };
            }
        }
    } else if (data.fetching_urls && data.fetching_urls.length > 0 && taskHistory.length > 0) {
        const lastQueryIndex = taskHistory.length - 1;
        const lastEntry = taskHistory[lastQueryIndex];
        const existingUrls = new Set(lastEntry.urls.map(u => u.url));
        const newUrls = data.fetching_urls.filter(u => !existingUrls.has(u.url));
        if (newUrls.length > 0) {
            taskHistory[lastQueryIndex] = {
                ...lastEntry,
                urls: [...lastEntry.urls, ...newUrls],
            };
        }
    }

    deepResearchQueryHistory.set(currentTaskIdFromResult, taskHistory);

    return taskHistory;
}

function processToolResultRag(data: ToolResultPayload, prevRagData: RAGSearchResult[], currentTaskIdFromResult: string | undefined): RAGSearchResult[] | undefined {
    const resultData = data.result_data;
    if (!resultData || !resultData.rag_metadata) {
        return undefined;
    }

    const ragMetadata = resultData.rag_metadata;
    const ragSearchResult: RAGSearchResult = {
        query: ragMetadata.query,
        title: ragMetadata.title,
        searchType: ragMetadata.searchType,
        timestamp: ragMetadata.timestamp,
        sources: ragMetadata.sources,
        taskId: currentTaskIdFromResult,
        metadata: ragMetadata.metadata,
    };

    if (ragMetadata.searchType === "deep_research") {
        const filtered = prevRagData.filter(r => !(r.searchType === "deep_research" && r.taskId === currentTaskIdFromResult));
        return [...filtered, ragSearchResult];
    } else {
        return [...prevRagData, ragSearchResult];
    }
}

function applyContentToMessages(
    inputMessages: MessageFE[],
    newContentParts: Part[],
    options: {
        hasNewFiles: boolean;
        isFinalEvent: boolean;
        isTaskFailed: boolean;
        taskId: string | undefined;
        eventSequence: number;
        messageId: string;
        contextId: string | undefined;
        fallbackSessionId: string;
    }
): MessageFE[] {
    const { hasNewFiles, isFinalEvent, isTaskFailed, taskId, eventSequence, messageId, contextId, fallbackSessionId } = options;
    const messages = [...inputMessages];
    let lastMessage = messages[messages.length - 1];

    // Remove old generic status bubble
    if (lastMessage?.isStatusBubble) {
        messages.pop();
        lastMessage = messages[messages.length - 1];
    }

    const isProgressUpdate = newContentParts.length === 1 && newContentParts[0].kind === "data" && (newContentParts[0] as DataPart).data && (newContentParts[0] as DataPart).data?.type === "deep_research_progress";

    if (isProgressUpdate && lastMessage && !lastMessage.isUser && lastMessage.taskId === taskId) {
        messages[messages.length - 1] = {
            ...lastMessage,
            parts: newContentParts as PartFE[],
            isComplete: isFinalEvent || hasNewFiles,
            metadata: {
                ...lastMessage.metadata,
                lastProcessedEventSequence: eventSequence,
            },
        };
    } else if (isCompactionNotificationBubble(lastMessage, taskId ?? "", newContentParts)) {
        messages.push({
            role: "agent",
            parts: newContentParts as PartFE[],
            taskId,
            isUser: false,
            isComplete: isFinalEvent,
            metadata: {
                messageId,
                sessionId: contextId ?? fallbackSessionId,
                lastProcessedEventSequence: eventSequence,
            },
        });
    } else if (lastMessage && !lastMessage.isUser && lastMessage.taskId === taskId && newContentParts.length > 0) {
        messages[messages.length - 1] = {
            ...lastMessage,
            parts: [...lastMessage.parts, ...(newContentParts as PartFE[])],
            isComplete: isFinalEvent || hasNewFiles,
            isError: isTaskFailed || lastMessage.isError,
            metadata: {
                ...lastMessage.metadata,
                lastProcessedEventSequence: eventSequence,
            },
        };
    } else if (isTaskFailed || checkHasVisibleContent(newContentParts)) {
        messages.push({
            role: "agent",
            parts: newContentParts as PartFE[],
            taskId,
            isUser: false,
            isComplete: isFinalEvent || hasNewFiles,
            isError: isTaskFailed,
            metadata: {
                messageId,
                sessionId: contextId ?? fallbackSessionId,
                lastProcessedEventSequence: eventSequence,
            },
        });
    }

    return messages;
}
