/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useCallback, useEffect, useRef, type FormEvent, type ReactNode } from "react";
import { v4 as uuidv4 } from "uuid";
import { useBooleanFlagDetails } from "@openfeature/react-sdk";

import { api } from "@/lib/api";
import { ChatContext, type ChatContextValue, type PendingPromptData } from "@/lib/contexts";
import { useConfigContext, useArtifacts, useAgentCards, useTaskContext, useErrorDialog, useBackgroundTaskMonitor, useArtifactPreview, useArtifactOperations, useCollaborativeSession } from "@/lib/hooks";
import { useAutoGenerateTitle } from "@/lib/hooks/useAutoGenerateTitle";
import { useProjectContext, registerProjectDeletedCallback } from "@/lib/providers";
import { processChatEvent, serializeChatMessage, deserializeChatMessages } from "@/lib/providers/chat";
import type { ChatEffect } from "@/lib/providers/chat";
import { getErrorMessage, fileToBase64, migrateTask, CURRENT_SCHEMA_VERSION, getApiBearerToken, internalToDisplayText, extractRagDataFromTasks } from "@/lib/utils";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";

import type {
    CancelTaskRequest,
    FilePart,
    Message,
    MessageFE,
    Notification,
    Part,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Session,
    Task,
    TextPart,
    ArtifactPart,
    AgentCardInfo,
    Project,
    StoredTaskData,
    RAGSearchResult,
    ArtifactInfo,
} from "@/lib/types";

// Wrapper to force uuid to use crypto.getRandomValues() fallback instead of crypto.randomUUID()
// This ensures compatibility with non-secure (HTTP) contexts where crypto.randomUUID() is unavailable
// Note: may be able to remove this workaround with next version of uuid
const v4 = () => uuidv4({});

const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    // ============ Hooks ============
    const { configWelcomeMessage, persistenceEnabled, configCollectFeedback, backgroundTasksEnabled, backgroundTasksDefaultTimeoutMs, configUseAuthorization } = useConfigContext();
    const { value: inlineActivityTimelineEnabled } = useBooleanFlagDetails("inline_activity_timeline", false);
    const { value: showThinkingContentEnabled } = useBooleanFlagDetails("show_thinking_content", false);
    const { activeProject, setActiveProject, projects } = useProjectContext();
    const { registerTaskEarly } = useTaskContext();
    const { ErrorDialog, setError } = useErrorDialog();
    const { agents, agentNameMap: agentNameDisplayNameMap, error: agentsError, isLoading: agentsLoading, refetch: agentsRefetch } = useAgentCards();
    const { autoTitleGenerationEnabled, autoGenerateTitle, autoGenerateTitleForTask } = useAutoGenerateTitle();

    // ============ State ============
    const [sessionId, setSessionId] = useState<string>("");
    const [messages, _setMessages] = useState<MessageFE[]>([]);
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [ragData, _setRagData] = useState<RAGSearchResult[]>([]);
    const [ragEnabled] = useState<boolean>(true);
    const [expandedDocumentFilename, setExpandedDocumentFilename] = useState<string | null>(null);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false);
    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState<boolean>(true);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "activity" | "rag">("files");
    const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, { type: "up" | "down"; text: string }>>({});
    const [pendingPrompt, setPendingPrompt] = useState<PendingPromptData | null>(null);
    const [runningTaskWarningOpen, setRunningTaskWarningOpen] = useState<boolean>(false);
    const [pendingNavigationAction, setPendingNavigationAction] = useState<(() => void) | null>(null);

    // ============ Hooks that depend on state ============
    const { isCollaborativeSession, hasSharedEditors, currentUserEmail, sessionOwnerName, sessionOwnerEmail, detectCollaborativeSession, resetCollaborativeState, getCurrentUserId } = useCollaborativeSession(sessionId);
    const { artifacts, allArtifacts, isLoading: artifactsLoading, refetch: artifactsRefetch, setArtifacts, showWorkingArtifacts, toggleShowWorkingArtifacts, workingArtifactCount } = useArtifacts(sessionId);

    // ============ Refs ============
    // Refs serve two purposes here which may be replaceable by a react-state-management library.
    // 1. Mirroring state for SSE event handlers that would otherwise capture stale closure values
    //    (e.g., messagesRef, ragDataRef, isCancellingRef, currentSessionIdRef)
    // 2. Holding mutable values that don't trigger re-renders
    //    (e.g., cancelTimeoutRef, isFinalizing, savingTasksRef)
    const ragDataRef = useRef<RAGSearchResult[]>([]);
    const isCancellingRef = useRef(isCancelling);
    const currentSessionIdRef = useRef(sessionId);
    const messagesRef = useRef<MessageFE[]>([]);
    const allArtifactsRef = useRef<ArtifactInfo[]>([]);
    const backgroundTasksRef = useRef<typeof backgroundTasks>([]);
    const inlineActivityTimelineEnabledRef = useRef(inlineActivityTimelineEnabled);
    const showThinkingContentEnabledRef = useRef(showThinkingContentEnabled);
    const currentEventSource = useRef<EventSource | null>(null);
    const savingTasksRef = useRef<Set<string>>(new Set());
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);
    const replayBufferedEventsRef = useRef<((taskId: string) => Promise<boolean>) | null>(null);
    const handleSseMessageRef = useRef<((event: MessageEvent) => void) | null>(null);
    const isReplayingEventsRef = useRef(false);
    const deepResearchQueryHistoryRef = useRef<
        Map<
            string,
            Array<{
                query: string;
                timestamp: string;
                urls: Array<{ url: string; title: string; favicon: string; source_type?: string }>;
            }>
        >
    >(new Map());

    // ============ Ref sync ============
    // Keep refs in sync with their corresponding state/hook values.
    useEffect(() => {
        inlineActivityTimelineEnabledRef.current = inlineActivityTimelineEnabled;
    }, [inlineActivityTimelineEnabled]);
    useEffect(() => {
        showThinkingContentEnabledRef.current = showThinkingContentEnabled;
    }, [showThinkingContentEnabled]);
    useEffect(() => {
        isCancellingRef.current = isCancelling;
    }, [isCancelling]);
    useEffect(() => {
        currentSessionIdRef.current = sessionId;
    }, [sessionId]);
    // allArtifactsRef has two write paths:
    // 1. This useEffect syncs when artifacts load from the API (session switch, initial fetch).
    // 2. handleSseMessage writes synchronously for SSE freshness during streaming.
    // Both are needed: the useEffect seeds the ref; the sync write prevents stale reads between events.
    useEffect(() => {
        allArtifactsRef.current = allArtifacts;
    }, [allArtifacts]);

    // Refs that handle events that may be coming in faster than state updates — a callback
    // ensures the ref is updated synchronously inside the state setter, minimizing staleness.
    const setMessages = useCallback((data: MessageFE[] | ((prev: MessageFE[]) => MessageFE[])) => {
        _setMessages(prev => {
            const newData = typeof data === "function" ? data(prev) : data;
            messagesRef.current = newData;
            return newData;
        });
    }, []);
    const setRagData = useCallback((data: RAGSearchResult[] | ((prev: RAGSearchResult[]) => RAGSearchResult[])) => {
        _setRagData(prev => {
            const newData = typeof data === "function" ? data(prev) : data;
            ragDataRef.current = newData;
            return newData;
        });
    }, []);

    // Notification Helper
    const addNotification = useCallback((message: string, type?: "success" | "info" | "warning") => {
        setNotifications(prev => {
            const existingNotification = prev.find(n => n.message === message);

            if (existingNotification) {
                return prev;
            }

            const id = Date.now().toString();
            const newNotification = { id, message, type: type || "info" };

            setTimeout(() => {
                setNotifications(current => current.filter(n => n.id !== id));
            }, 4000);

            return [...prev, newNotification];
        });
    }, []);

    // Artifact Preview
    const {
        preview: { availableVersions: previewedArtifactAvailableVersions, currentVersion: currentPreviewedVersionNumber, content: previewFileContent },
        previewArtifact,
        openPreview,
        navigateToVersion,
        closePreview,
        setPreviewByArtifact,
    } = useArtifactPreview({
        sessionId,
        projectId: activeProject?.id,
        artifacts: allArtifacts,
        setError,
    });

    // Artifact Operations
    const {
        uploadArtifactFile,

        isDeleteModalOpen,
        artifactToDelete,
        openDeleteModal,
        closeDeleteModal,
        confirmDelete,

        isArtifactEditMode,
        setIsArtifactEditMode,
        selectedArtifactFilenames,
        setSelectedArtifactFilenames,
        isBatchDeleteModalOpen,
        setIsBatchDeleteModalOpen,
        handleDeleteSelectedArtifacts,
        confirmBatchDeleteArtifacts,

        downloadAndResolveArtifact,
    } = useArtifactOperations({
        sessionId,
        artifacts,
        setArtifacts,
        artifactsRefetch,
        addNotification,
        setError,
        previewArtifact,
        closePreview,
    });

    // Get the authenticated user's ID for background task monitoring
    const authenticatedUserId = getCurrentUserId();

    const {
        backgroundTasks,
        notifications: backgroundNotifications,
        registerBackgroundTask,
        unregisterBackgroundTask,
        updateTaskTimestamp,
        isTaskRunningInBackground,
        checkTaskStatus,
    } = useBackgroundTaskMonitor({
        userId: authenticatedUserId,
        currentSessionId: sessionId,
        onTaskCompleted: useCallback(
            async (taskId: string, taskSessionId: string) => {
                // Only show notification if user is NOT currently viewing the session where the task completed
                // This reduces noise when the user is already on the chat page seeing the results
                if (currentSessionIdRef.current !== taskSessionId) {
                    addNotification("Background task completed", "success");
                }

                // Trigger session list refresh to update background task indicators
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("background-task-completed", {
                            detail: { taskId },
                        })
                    );
                    // Also trigger general session list refresh
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }

                // Trigger title generation for the completed background task
                await autoGenerateTitleForTask(taskId, backgroundTasksRef.current);
            },
            [addNotification, autoGenerateTitleForTask]
        ),
        onTaskFailed: useCallback(
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            (taskId: string, error: string, _taskSessionId: string) => {
                // Always show error dialog for failed tasks, regardless of current session
                // Errors are important and should not be silently ignored
                setError({ title: "Background Task Failed", error });

                // Trigger session list refresh to update background task indicators
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("background-task-completed", {
                            detail: { taskId },
                        })
                    );
                    // Also trigger general session list refresh
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            },
            [setError]
        ),
    });

    useEffect(() => {
        backgroundTasksRef.current = backgroundTasks;
    }, [backgroundTasks]);

    // Helper function to save task data to backend
    const saveTaskToBackend = useCallback(
        async (taskData: { task_id: string; user_message?: string; message_bubbles: any[]; task_metadata?: any }, overrideSessionId?: string): Promise<boolean> => {
            const effectiveSessionId = overrideSessionId || sessionId;

            if (!persistenceEnabled || !effectiveSessionId) {
                return false;
            }

            // Prevent duplicate saves (handles React Strict Mode + race conditions)
            if (savingTasksRef.current.has(taskData.task_id)) {
                return false;
            }

            // Mark as saving
            savingTasksRef.current.add(taskData.task_id);

            try {
                await api.webui.post(`/api/v1/sessions/${effectiveSessionId}/chat-tasks`, {
                    taskId: taskData.task_id,
                    userMessage: taskData.user_message,
                    messageBubbles: JSON.stringify(taskData.message_bubbles),
                    taskMetadata: taskData.task_metadata ? JSON.stringify(taskData.task_metadata) : null,
                });
                return true;
            } catch (error) {
                console.error(`Failed saving task ${taskData.task_id}:`, error);
                return false;
            } finally {
                // Always remove from saving set after a delay to handle rapid re-renders
                setTimeout(() => {
                    savingTasksRef.current.delete(taskData.task_id);
                }, 100);
            }
        },
        [sessionId, persistenceEnabled]
    );

    // Helper function to load session tasks and reconstruct messages
    const loadSessionTasks = useCallback(
        async (sessionId: string) => {
            const data = await api.webui.get(`/api/v1/sessions/${sessionId}/chat-tasks`);

            // Check if this session is still active before processing
            if (currentSessionIdRef.current !== sessionId) {
                console.log(`Session ${sessionId} is no longer the active session: ${currentSessionIdRef.current}`);
                return;
            }

            // Parse JSON strings from backend
            const tasks = data.tasks || [];
            const parsedTasks = tasks.map((task: StoredTaskData) => ({
                ...task,
                messageBubbles: JSON.parse(task.messageBubbles),
                taskMetadata: task.taskMetadata ? JSON.parse(task.taskMetadata) : null,
            }));

            // Apply migrations to each task
            const migratedTasks = parsedTasks.map(migrateTask);

            // Deserialize all tasks to messages
            const allMessages: MessageFE[] = [];

            // Track which tasks have buffered events (need replay)
            const tasksWithBufferedEvents = new Map<string, { events_buffered: boolean; events: any[] }>();

            if (replayBufferedEventsRef.current && backgroundTasksEnabled) {
                try {
                    // Use include_events=true to get all events in one batch
                    const response = await api.webui.get(`/api/v1/sessions/${sessionId}/events/unconsumed?include_events=true`);
                    if (response.has_events && response.events_by_task) {
                        // Populate the map from the batched response
                        for (const [taskId, taskEvents] of Object.entries(response.events_by_task)) {
                            const typedEvents = taskEvents as { events_buffered: boolean; events: any[] };
                            if (typedEvents.events_buffered && typedEvents.events.length > 0) {
                                console.debug(`[loadSessionTasks] Task ${taskId} has ${typedEvents.events.length} buffered events (batched)`);
                                tasksWithBufferedEvents.set(taskId, typedEvents);
                            }
                        }
                        console.debug(`[loadSessionTasks] Loaded buffered events for ${tasksWithBufferedEvents.size} tasks in single request`);
                    }
                } catch (error) {
                    // Fall back to per-task queries if batched endpoint fails
                    console.warn(`[loadSessionTasks] Batched event fetch failed, falling back to per-task queries:`, error);
                    for (const task of migratedTasks) {
                        try {
                            const response = await api.webui.get(`/api/v1/tasks/${task.taskId}/events/buffered?mark_consumed=false`);
                            if (response.events_buffered && response.events.length > 0) {
                                console.debug(`[loadSessionTasks] Task ${task.taskId} has ${response.events.length} buffered events (fallback)`);
                                tasksWithBufferedEvents.set(task.taskId, response);
                            }
                        } catch (taskError) {
                            console.debug(`[loadSessionTasks] Could not check buffered events for task ${task.taskId}:`, taskError);
                        }
                    }
                }
            }

            for (const task of migratedTasks) {
                const taskMessages = deserializeChatMessages(task, sessionId);

                if (tasksWithBufferedEvents.has(task.taskId)) {
                    const userMessages = taskMessages.filter(m => m.isUser);
                    allMessages.push(...userMessages);
                } else {
                    // No buffered events - add all messages from chat_tasks
                    allMessages.push(...taskMessages);
                }
            }

            // Extract feedback state from task metadata
            const feedbackMap: Record<string, { type: "up" | "down"; text: string }> = {};
            for (const task of migratedTasks) {
                let meta = null;
                try {
                    meta = typeof task.taskMetadata === "string" ? JSON.parse(task.taskMetadata) : task.taskMetadata;
                } catch {
                    // Malformed JSON in persisted metadata — skip gracefully
                }

                if (meta?.feedback) {
                    feedbackMap[task.taskId] = {
                        type: meta.feedback.type,
                        text: meta.feedback.text || "",
                    };
                }
            }

            // Extract RAG data from task metadata
            const allRagData = extractRagDataFromTasks(migratedTasks);

            // Extract agent name from the most recent task
            // (Use the last task's agent since that's the most recent interaction)
            let agentName: string | null = null;
            for (let i = migratedTasks.length - 1; i >= 0; i--) {
                let agentMeta = null;
                try {
                    agentMeta = typeof migratedTasks[i].taskMetadata === "string" ? JSON.parse(migratedTasks[i].taskMetadata) : migratedTasks[i].taskMetadata;
                } catch {
                    // Malformed JSON in persisted metadata — skip gracefully
                }
                if (agentMeta?.agent_name) {
                    agentName = agentMeta.agent_name;
                    break;
                }
            }

            // Update feedback state
            setSubmittedFeedback(feedbackMap);

            // Restore RAG data
            if (allRagData.length > 0) {
                setRagData(allRagData);
            }

            // Set the agent name if found
            if (agentName) {
                setSelectedAgentName(agentName);
            }

            // Set taskIdInSidePanel to the most recent task for workflow visualization
            if (migratedTasks.length > 0) {
                const mostRecentTask = migratedTasks[migratedTasks.length - 1];
                setTaskIdInSidePanel(mostRecentTask.taskId);
            }

            // Process messages and buffered events to build the final message array
            // We need to reconstruct agent responses from buffered events and insert them
            // in the correct position (after their corresponding user messages)
            if (replayBufferedEventsRef.current && tasksWithBufferedEvents.size > 0) {
                console.debug(`[loadSessionTasks] Processing ${migratedTasks.length} tasks with ${tasksWithBufferedEvents.size} having buffered events`);

                // Build the complete message array with proper ordering
                const finalMessages: MessageFE[] = [];

                // Track tasks where we used buffer reconstruction (need save + cleanup)
                const tasksNeedingSaveAndCleanup: string[] = [];
                // Track tasks where chat_tasks already exists but buffer needs cleanup (cleanup only, no save)
                const tasksNeedingBufferCleanupOnly: string[] = [];

                // Collect tasks that need buffer replay (no saved agent response)
                const tasksNeedingReplay: Array<{ taskId: string; events: any[] }> = [];

                for (const task of migratedTasks) {
                    const taskMessages = deserializeChatMessages(task, sessionId);
                    const bufferedData = tasksWithBufferedEvents.get(task.taskId);
                    const agentMessagesFromChatTasks = taskMessages.filter(m => !m.isUser);
                    const userMessages = taskMessages.filter(m => m.isUser);

                    // Check if any agent messages have artifact parts with "in-progress" status
                    // This indicates the artifact was being created when the user switched away
                    // and the buffer may contain completion events we need to replay
                    const hasIncompleteArtifacts = agentMessagesFromChatTasks.some(msg => msg.parts?.some(part => part.kind === "artifact" && (part as ArtifactPart).status === "in-progress"));

                    // IMPORTANT: If chat_tasks already has agent messages, PREFER them over buffer replay.
                    // The buffer should only be used when:
                    // 1. There are no agent messages saved yet (task was running when user switched away)
                    // 2. Buffer replay is needed for incomplete saves
                    // 3. There are incomplete artifacts that need status updates from buffered events
                    // This prevents issues with complex parsing of SSE events.
                    const needsBufferReplay = bufferedData && (agentMessagesFromChatTasks.length === 0 || hasIncompleteArtifacts);

                    if (needsBufferReplay) {
                        // Task has buffered events AND either no saved agent response OR incomplete artifacts - need replay
                        const reason = agentMessagesFromChatTasks.length === 0 ? "no saved agent response" : "incomplete artifacts";
                        console.debug(`[loadSessionTasks] Task ${task.taskId} has buffered events and ${reason}, will replay through handleSseMessage`);
                        // Add user messages first
                        finalMessages.push(...userMessages);
                        // Store for replay after we set initial messages
                        tasksNeedingReplay.push({ taskId: task.taskId, events: bufferedData.events });
                        // Mark this task for save and cleanup (will update session modified date)
                        tasksNeedingSaveAndCleanup.push(task.taskId);
                    } else {
                        // Either no buffered events OR chat_tasks already has the agent response with complete artifacts
                        // Use the saved data from chat_tasks (it has correct ordering)
                        if (bufferedData && agentMessagesFromChatTasks.length > 0) {
                            console.debug(
                                `[loadSessionTasks] Task ${task.taskId} has buffered events but also has ${agentMessagesFromChatTasks.length} saved agent messages with complete artifacts - preferring chat_tasks data, scheduling buffer cleanup only`
                            );
                            // Chat task already exists - only clean up the buffer (don't re-save to avoid updating modified date)
                            tasksNeedingBufferCleanupOnly.push(task.taskId);
                        }
                        finalMessages.push(...taskMessages);
                    }
                }

                // Set all messages in ONE batch to avoid scroll issues
                setMessages(finalMessages);

                // Replay buffered events through handleSseMessage (uses exact same code path as live streaming!)
                // This is done AFTER setting initial messages so user messages are visible first
                if (tasksNeedingReplay.length > 0) {
                    console.debug(`[loadSessionTasks] Replaying ${tasksNeedingReplay.length} tasks through handleSseMessage`);

                    // Use setTimeout to not block the UI update
                    setTimeout(async () => {
                        // Get the current handleSseMessage function via ref
                        const handleSseMessageFn = handleSseMessageRef.current;
                        if (!handleSseMessageFn) {
                            console.error(`[loadSessionTasks] handleSseMessageRef not available for replay`);
                            return;
                        }

                        for (const { taskId, events } of tasksNeedingReplay) {
                            console.debug(`[loadSessionTasks] Replaying ${events.length} events for task ${taskId}`);

                            // Set replay flag to prevent saves during replay (state updates are async)
                            isReplayingEventsRef.current = true;

                            try {
                                // Process each buffered event through handleSseMessage
                                // This is the EXACT same code path as live SSE streaming!
                                for (const bufferedEvent of events) {
                                    const ssePayload = bufferedEvent.data;
                                    if (ssePayload?.data) {
                                        // Create a synthetic MessageEvent-like object
                                        const syntheticEvent = {
                                            data: ssePayload.data,
                                        } as MessageEvent;

                                        // Process through SSE handler - exact same as live streaming
                                        handleSseMessageFn(syntheticEvent);
                                    }
                                }
                            } finally {
                                isReplayingEventsRef.current = false;
                            }
                        }

                        // After replay, get messages and save using setMessages functional updater
                        const taskIdsToSave = tasksNeedingReplay.map(t => t.taskId);
                        setMessages(currentMessages => {
                            setTimeout(async () => {
                                for (const taskId of taskIdsToSave) {
                                    const taskMessages = currentMessages.filter(m => m.taskId === taskId && !m.isStatusBubble);
                                    if (taskMessages.length > 0) {
                                        console.debug(`[loadSessionTasks] Saving task ${taskId} after replay (${taskMessages.length} messages)`);
                                        const messageBubbles = taskMessages.map(serializeChatMessage);
                                        const userMessage = taskMessages.find(m => m.isUser);
                                        const userMessageText =
                                            userMessage?.parts
                                                ?.filter(p => p.kind === "text")
                                                .map(p => (p as TextPart).text)
                                                .join("") || "";
                                        const hasError = taskMessages.some(m => m.isError);
                                        const taskStatus = hasError ? "error" : "completed";

                                        await saveTaskToBackend(
                                            {
                                                task_id: taskId,
                                                user_message: userMessageText,
                                                message_bubbles: messageBubbles,
                                                task_metadata: {
                                                    schema_version: CURRENT_SCHEMA_VERSION,
                                                    status: taskStatus,
                                                },
                                            },
                                            sessionId
                                        );
                                    } else {
                                        console.warn(`[loadSessionTasks] No messages found for task ${taskId} after replay`);
                                    }
                                }
                            }, 0);
                            // Return unchanged - we're just reading state
                            return currentMessages;
                        });
                    }, 50);
                }

                // Trigger buffer cleanup only (no save) for tasks where chat_tasks already exists
                // This avoids updating the session's modified date just from visiting it
                if (tasksNeedingBufferCleanupOnly.length > 0) {
                    console.debug(`[loadSessionTasks] Scheduling buffer cleanup only for ${tasksNeedingBufferCleanupOnly.length} tasks`);
                    setTimeout(async () => {
                        for (const taskId of tasksNeedingBufferCleanupOnly) {
                            try {
                                await api.webui.delete(`/api/v1/tasks/${taskId}/events/buffered`);
                                console.debug(`[loadSessionTasks] Buffer cleanup successful for task ${taskId}`);
                            } catch (error) {
                                console.error(`[loadSessionTasks] Failed to clean up buffer for task ${taskId}:`, error);
                            }
                        }
                    }, 100);
                }
            } else {
                // No tasks with buffered events - just set all messages at once
                setMessages(allMessages);
            }

            // Collaborative session detection happens in switchSession via useCollaborativeSession hook.
            // Sender info in messages is kept for UI display purposes only.
        },
        [backgroundTasksEnabled, setRagData, setMessages, saveTaskToBackend]
    );

    // Session State
    const [sessionName, setSessionName] = useState<string | null>(null);
    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);
    const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);

    const openSidePanelTab = useCallback((tab: "files" | "activity" | "rag") => {
        setIsSidePanelCollapsed(false);
        setActiveSidePanelTab(tab);

        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("expand-side-panel", {
                    detail: { tab },
                })
            );
        }
    }, []);

    const closeCurrentEventSource = useCallback(() => {
        if (cancelTimeoutRef.current) {
            clearTimeout(cancelTimeoutRef.current);
            cancelTimeoutRef.current = null;
        }

        if (currentEventSource.current) {
            // Listeners are now removed in the useEffect cleanup
            currentEventSource.current.close();
            currentEventSource.current = null;
        }
        isFinalizing.current = false;
    }, []);

    // Execute a side-effect descriptor returned by processChatEvent
    const executeEffect = useCallback(
        (effect: ChatEffect) => {
            switch (effect.type) {
                case "close-connection":
                    closeCurrentEventSource();
                    break;
                case "stop-responding":
                    setIsResponding(false);
                    break;
                case "clear-task-id":
                    setCurrentTaskId(null);
                    break;
                case "cancel-complete":
                    if (isCancellingRef.current) {
                        addNotification("Task cancelled.", "success");
                        if (cancelTimeoutRef.current) clearTimeout(cancelTimeoutRef.current);
                        setIsCancelling(false);
                    }
                    break;
                case "refetch-artifacts":
                    void artifactsRefetch();
                    break;
                case "save-task": {
                    const { taskId, messages: taskMessages, sessionId: taskSessionId, selectedAgentName: agentName, ragData: taskRagData } = effect.payload;
                    // taskMessages is already filtered by processChatEvent (taskId match, no status bubbles)
                    if (taskMessages.length === 0) break;

                    const isBackgroundTask = isTaskRunningInBackground(taskId);
                    const messageBubbles = taskMessages.map(serializeChatMessage);

                    const userMessage = taskMessages.find(m => m.isUser);
                    const userMessageText =
                        userMessage?.parts
                            ?.filter(p => p.kind === "text")
                            .map(p => (p as TextPart).text)
                            .join("") || "";

                    const hasError = taskMessages.some(m => m.isError);
                    const taskStatus = hasError ? "error" : "completed";

                    saveTaskToBackend(
                        {
                            task_id: taskId,
                            user_message: userMessageText,
                            message_bubbles: messageBubbles,
                            task_metadata: {
                                schema_version: CURRENT_SCHEMA_VERSION,
                                status: taskStatus,
                                agent_name: agentName,
                                rag_data: taskRagData.length > 0 ? taskRagData : undefined,
                            },
                        },
                        taskSessionId
                    )
                        .then(async saved => {
                            if (saved) {
                                if (typeof window !== "undefined") {
                                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                                }
                            }

                            if (isBackgroundTask) {
                                unregisterBackgroundTask(taskId);
                            }

                            if (taskSessionId) {
                                const agentMessage = taskMessages.find(m => !m.isUser);
                                const agentResponseText =
                                    agentMessage?.parts
                                        ?.filter(p => p.kind === "text")
                                        .map(p => (p as TextPart).text)
                                        .join("") || "";

                                autoGenerateTitle(taskSessionId, userMessageText, agentResponseText);
                            }
                        })
                        .catch(error => {
                            console.error(`[ChatProvider] Error saving task ${taskId}:`, error);
                            if (isBackgroundTask) {
                                unregisterBackgroundTask(taskId);
                            }
                        });
                    break;
                }
                case "unregister-background-task":
                    unregisterBackgroundTask(effect.payload.taskId);
                    break;
                case "update-task-timestamp":
                    updateTaskTimestamp(effect.payload.taskId, effect.payload.timestamp);
                    break;
                case "auto-download-artifact":
                    setTimeout(() => {
                        downloadAndResolveArtifact(effect.payload.filename).catch(err => {
                            console.error(`Auto-download failed for ${effect.payload.filename}:`, err);
                        });
                    }, 100);
                    break;
                case "dispatch-new-chat-session":
                    if (typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                    break;
                case "finalize":
                    isFinalizing.current = true;
                    setTimeout(() => {
                        isFinalizing.current = false;
                    }, 100);
                    break;
            }
        },

        [addNotification, closeCurrentEventSource, artifactsRefetch, saveTaskToBackend, downloadAndResolveArtifact, isTaskRunningInBackground, updateTaskTimestamp, unregisterBackgroundTask, autoGenerateTitle]
    );

    const handleSseMessage = useCallback(
        (event: MessageEvent) => {
            sseEventSequenceRef.current += 1;

            const output = processChatEvent({
                eventData: event.data,
                messages: messagesRef.current,
                ragData: ragDataRef.current,
                artifacts: allArtifactsRef.current,
                flags: {
                    inlineActivityTimeline: inlineActivityTimelineEnabledRef.current,
                    showThinkingContent: showThinkingContentEnabledRef.current,
                    ragEnabled,
                    isReplaying: isReplayingEventsRef.current,
                },
                sessionId: currentSessionIdRef.current,
                selectedAgentName,
                deepResearchQueryHistory: deepResearchQueryHistoryRef.current,
                eventSequence: sseEventSequenceRef.current,
                isTaskRunningInBackground,
            });

            // Apply state updates
            if (output.messages) {
                messagesRef.current = output.messages;
                setMessages(output.messages);
            }
            if (output.ragData) {
                setRagData(output.ragData);
            }
            if (output.artifacts) {
                allArtifactsRef.current = output.artifacts;
                setArtifacts(output.artifacts);
            }
            if (output.latestStatusText !== undefined) {
                latestStatusText.current = output.latestStatusText;
            }
            if (output.deepResearchQueryHistory) {
                deepResearchQueryHistoryRef.current = output.deepResearchQueryHistory;
            }

            // Execute side effects
            for (const effect of output.effects) {
                executeEffect(effect);
            }
        },

        [ragEnabled, selectedAgentName, isTaskRunningInBackground, setMessages, setRagData, setArtifacts, executeEffect]
    );
    // Helper function to replay buffered SSE events for a background task
    // This is used when a background task completed while the user was away
    const replayBufferedEvents = useCallback(
        async (taskId: string): Promise<boolean> => {
            try {
                console.debug(`[ChatProvider] Fetching buffered events for task ${taskId}`);
                const response = await api.webui.get(`/api/v1/tasks/${taskId}/events/buffered`);

                if (!response.events_buffered || response.events.length === 0) {
                    console.debug(`[ChatProvider] No buffered events for task ${taskId}`);
                    return false;
                }

                console.debug(`[ChatProvider] Replaying ${response.events.length} buffered events for task ${taskId}`);

                // Reset the SSE event sequence counter for replay
                // This ensures proper sequencing during replay
                const originalSequence = sseEventSequenceRef.current;
                sseEventSequenceRef.current = 0;

                // Clear any existing AGENT messages for this task before replaying
                // Keep user messages since they're not in the SSE events
                // This prevents duplicate content when replaying while preserving user input
                setMessages(prev => prev.filter(msg => msg.taskId !== taskId || msg.isUser));

                // Set the replay flag to prevent save operations during replay
                // The data is already persisted, so we don't want to re-save and update timestamps
                isReplayingEventsRef.current = true;

                try {
                    // Process each buffered event through the SSE handler
                    for (const bufferedEvent of response.events) {
                        // The buffered event data contains the full SSE payload
                        // which has {event: "message", data: "...serialized JSON..."}
                        const ssePayload = bufferedEvent.data;

                        if (ssePayload?.data) {
                            // Create a synthetic MessageEvent-like object
                            const syntheticEvent = {
                                data: ssePayload.data, // This is the serialized JSON string
                            } as MessageEvent;

                            // Process through the SSE handler
                            handleSseMessage(syntheticEvent);
                        }
                    }
                } finally {
                    // Always reset the replay flag, even if an error occurred
                    isReplayingEventsRef.current = false;
                }

                // Restore the sequence counter (or keep the new value if higher)
                sseEventSequenceRef.current = Math.max(originalSequence, sseEventSequenceRef.current);

                console.debug(`[ChatProvider] Finished replaying buffered events for task ${taskId}`);
                return true;
            } catch (error) {
                console.error(`[ChatProvider] Error replaying buffered events for task ${taskId}:`, error);
                isReplayingEventsRef.current = false; // Reset flag on error
                return false;
            }
        },
        [handleSseMessage, setMessages]
    );

    // Keep the ref in sync with the latest replayBufferedEvents function
    useEffect(() => {
        replayBufferedEventsRef.current = replayBufferedEvents;
    }, [replayBufferedEvents]);

    // Core implementation - called directly or after confirmation
    const handleNewSessionCore = useCallback(
        async (preserveProjectContext: boolean = false) => {
            const log_prefix = "ChatProvider.handleNewSession:";

            closeCurrentEventSource();

            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                const isBackground = isTaskRunningInBackground(currentTaskId);
                if (!isBackground) {
                    api.webui
                        .post(`/api/v1/tasks/${currentTaskId}:cancel`, {
                            jsonrpc: "2.0",
                            id: `req-${v4()}`,
                            method: "tasks/cancel",
                            params: { id: currentTaskId },
                        })
                        .catch(error => console.warn(`${log_prefix} Failed to cancel current task:`, error));
                }
            }

            if (cancelTimeoutRef.current) {
                clearTimeout(cancelTimeoutRef.current);
                cancelTimeoutRef.current = null;
            }
            setIsCancelling(false);

            // Clear session ID - will be set by backend when first message is sent
            setSessionId("");

            // Clear session name - will be set when first message is sent
            setSessionName(null);

            // Reset collaborative session flag - new sessions are always owned by the current user
            resetCollaborativeState();

            // Clear project context when starting a new chat outside of a project
            if (activeProject && !preserveProjectContext) {
                setActiveProject(null);
            } else if (activeProject && preserveProjectContext) {
                console.log(`${log_prefix} Preserving project context: ${activeProject.name}`);
            }

            setSelectedAgentName("");
            setMessages([]);
            setIsResponding(false);
            setCurrentTaskId(null);
            setTaskIdInSidePanel(null);
            closePreview();
            isFinalizing.current = false;
            latestStatusText.current = null;

            sseEventSequenceRef.current = 0;
            // Clear RAG data on new session
            setRagData([]);
            // Clear deep research query history
            deepResearchQueryHistoryRef.current.clear();
            // Artifacts will be automatically refreshed by useArtifacts hook when sessionId changes

            // Dispatch event to focus chat input
            if (typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("focus-chat-input"));
            }

            // Note: No session events dispatched here since no session exists yet.
            // Session creation event will be dispatched when first message creates the actual session.
        },
        [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, resetCollaborativeState, activeProject, setMessages, closePreview, setRagData, isTaskRunningInBackground, setActiveProject]
    );

    // Wrapper that shows confirmation when task is running and background tasks are disabled
    const handleNewSession = useCallback(
        async (preserveProjectContext: boolean = false) => {
            // Check if we need to warn the user about losing a running task
            if (isResponding && backgroundTasksEnabled === false) {
                // Store the action to execute after confirmation
                setPendingNavigationAction(() => () => handleNewSessionCore(preserveProjectContext));
                setRunningTaskWarningOpen(true);
                return;
            }
            // No warning needed - proceed directly
            await handleNewSessionCore(preserveProjectContext);
        },
        [isResponding, backgroundTasksEnabled, handleNewSessionCore]
    );

    // Start a new chat session with a prompt template pre-filled
    const startNewChatWithPrompt = useCallback(
        (promptData: PendingPromptData) => {
            // Store the pending prompt - it will be applied after the session is ready
            setPendingPrompt(promptData);
            // Start a new session
            handleNewSession();
        },
        [handleNewSession]
    );

    // Clear the pending prompt (called after it's been applied)
    const clearPendingPrompt = useCallback(() => {
        setPendingPrompt(null);
    }, []);

    // Core implementation - called directly or after confirmation
    const handleSwitchSessionCore = useCallback(
        async (newSessionId: string) => {
            const log_prefix = "ChatProvider.handleSwitchSession:";
            console.log(`${log_prefix} Switching to session ${newSessionId}...`);

            setIsLoadingSession(true);

            // Check if we're switching away from a session with a running background task
            const currentSessionBackgroundTasks = backgroundTasks.filter(t => t.sessionId === sessionId);
            const hasRunningBackgroundTask = currentSessionBackgroundTasks.some(t => t.taskId === currentTaskId);

            // DON'T clear messages if there are background tasks in the current session
            // This ensures the messages are available for saving when the task completes
            const hasAnyBackgroundTasks = currentSessionBackgroundTasks.length > 0;

            if (!hasRunningBackgroundTask && !hasAnyBackgroundTasks) {
                setMessages([]);
            }

            closeCurrentEventSource();

            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                const isBackground = isTaskRunningInBackground(currentTaskId);
                if (!isBackground) {
                    console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
                    try {
                        await api.webui.post(`/api/v1/tasks/${currentTaskId}:cancel`, {
                            jsonrpc: "2.0",
                            id: `req-${v4()}`,
                            method: "tasks/cancel",
                            params: { id: currentTaskId },
                        });
                    } catch (error) {
                        console.warn(`${log_prefix} Failed to cancel current task:`, error);
                    }
                }
            }

            if (cancelTimeoutRef.current) {
                clearTimeout(cancelTimeoutRef.current);
                cancelTimeoutRef.current = null;
            }
            setIsCancelling(false);

            try {
                // Load session metadata first to get project info
                const sessionData = await api.webui.get(`/api/v1/sessions/${newSessionId}`);
                const session: Session | null = sessionData?.data;
                setSessionName(session?.name ?? "N/A");

                // Detect collaborative session (owner differs from current user)
                await detectCollaborativeSession(session, newSessionId);

                // Activate or deactivate project context based on session's project
                // Set flag to prevent handleNewSession from being triggered by this project change
                isSessionSwitchRef.current = true;

                if (session?.projectId) {
                    console.log(`${log_prefix} Session belongs to project ${session.projectId}`);

                    // Check if we're already in the correct project context
                    if (activeProject?.id !== session.projectId) {
                        // Find the full project object from the projects array
                        const project = projects.find((p: Project) => p.id === session?.projectId);

                        if (project) {
                            console.log(`${log_prefix} Activating project context: ${project.name}`);
                            setActiveProject(project);
                        } else {
                            console.warn(`${log_prefix} Project ${session.projectId} not found in projects array`);
                        }
                    } else {
                        console.log(`${log_prefix} Already in correct project context`);
                    }
                } else {
                    // Session has no project - deactivate project context
                    if (activeProject !== null) {
                        console.log(`${log_prefix} Session has no project, deactivating project context`);
                        setActiveProject(null);
                    }
                }

                // Update session ID state
                setSessionId(newSessionId);

                // Reset other session-related state
                setIsResponding(false);
                setCurrentTaskId(null);
                setTaskIdInSidePanel(null);
                closePreview();
                // Reset refs
                isFinalizing.current = false;
                latestStatusText.current = null;
                sseEventSequenceRef.current = 0;
                setRagData([]);
                deepResearchQueryHistoryRef.current.clear();

                await loadSessionTasks(newSessionId);

                // Check for running background tasks in this session and reconnect
                const sessionBackgroundTasks = backgroundTasks.filter(t => t.sessionId === newSessionId);
                if (sessionBackgroundTasks.length > 0) {
                    // Check if any are still running
                    for (const bgTask of sessionBackgroundTasks) {
                        const status = await checkTaskStatus(bgTask.taskId);
                        if (status && status.is_running) {
                            console.log(`[ChatProvider] Reconnecting to running background task ${bgTask.taskId}`);
                            setCurrentTaskId(bgTask.taskId);
                            setIsResponding(true);
                            if (bgTask.agentName) {
                                setSelectedAgentName(bgTask.agentName);
                            }
                            // Only reconnect to the first running task
                            break;
                        } else {
                            // Task is no longer running - it completed while we were away
                            console.log(`[ChatProvider] Background task ${bgTask.taskId} completed while away, already reconstructed in loadSessionTasks`);

                            // Unregister the background task
                            unregisterBackgroundTask(bgTask.taskId);

                            // Trigger title generation for completed background task
                            autoGenerateTitleForTask(bgTask.taskId, backgroundTasks);
                        }
                    }
                }
            } catch (error) {
                setError({ title: "Switching Chats Failed", error: getErrorMessage(error, "Failed to switch chat sessions.") });
            } finally {
                setIsLoadingSession(false);
            }
        },
        [
            backgroundTasks,
            closeCurrentEventSource,
            isResponding,
            currentTaskId,
            selectedAgentName,
            isCancelling,
            sessionId,
            setMessages,
            isTaskRunningInBackground,
            detectCollaborativeSession,
            closePreview,
            setRagData,
            loadSessionTasks,
            activeProject,
            projects,
            setActiveProject,
            checkTaskStatus,
            unregisterBackgroundTask,
            autoGenerateTitleForTask,
            setError,
        ]
    );

    // Wrapper that shows confirmation when task is running and background tasks are disabled
    const handleSwitchSession = useCallback(
        async (newSessionId: string) => {
            // Check if we need to warn the user about losing a running task
            if (isResponding && backgroundTasksEnabled === false) {
                // Store the action to execute after confirmation
                setPendingNavigationAction(() => () => handleSwitchSessionCore(newSessionId));
                setRunningTaskWarningOpen(true);
                return;
            }
            // No warning needed - proceed directly
            await handleSwitchSessionCore(newSessionId);
        },
        [isResponding, backgroundTasksEnabled, handleSwitchSessionCore]
    );

    const updateSessionName = useCallback(
        async (sessionId: string, newName: string) => {
            try {
                const response = await api.webui.patch(`/api/v1/sessions/${sessionId}`, { name: newName }, { fullResponse: true });

                if (response.status === 422) {
                    throw new Error("Invalid name");
                }

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.message || "Failed to update session name");
                }

                setSessionName(newName);
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                setError({ title: "Session Name Update Failed", error: getErrorMessage(error, "Failed to update session name.") });
            }
        },
        [setError]
    );

    const deleteSession = useCallback(
        async (sessionIdToDelete: string) => {
            try {
                await api.webui.delete(`/api/v1/sessions/${sessionIdToDelete}`);
                addNotification("Session deleted.", "success");
                if (sessionIdToDelete === sessionId) {
                    handleNewSession();
                }
                // Trigger session list refresh
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                setError({ title: "Chat Deletion Failed", error: getErrorMessage(error, "Failed to delete session.") });
            }
        },
        [addNotification, handleNewSession, sessionId, setError]
    );

    // Artifact Display and Cache Management
    const markArtifactAsDisplayed = useCallback((filename: string, displayed: boolean) => {
        setArtifacts(prevArtifacts => {
            return prevArtifacts.map(artifact => (artifact.filename === filename ? { ...artifact, isDisplayed: displayed } : artifact));
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // setArtifacts is stable from useState

    const openSessionDeleteModal = useCallback((session: Session) => {
        setSessionToDelete(session);
    }, []);

    const closeSessionDeleteModal = useCallback(() => {
        setSessionToDelete(null);
    }, []);

    const confirmSessionDelete = useCallback(async () => {
        if (sessionToDelete) {
            await deleteSession(sessionToDelete.id);
            setSessionToDelete(null);
        }
    }, [sessionToDelete, deleteSession]);

    const handleCancel = useCallback(async () => {
        if ((!isResponding && !isCancelling) || !currentTaskId) {
            return;
        }
        if (isCancelling) {
            return;
        }

        setIsCancelling(true);

        try {
            const cancelRequest: CancelTaskRequest = {
                jsonrpc: "2.0",
                id: `req-${v4()}`,
                method: "tasks/cancel",
                params: { id: currentTaskId },
            };

            const response = await api.webui.post(`/api/v1/tasks/${currentTaskId}:cancel`, cancelRequest, { fullResponse: true });

            if (response.status === 202) {
                if (cancelTimeoutRef.current) clearTimeout(cancelTimeoutRef.current);
                cancelTimeoutRef.current = setTimeout(() => {
                    addNotification("Cancellation timed out. Allowing new input.");
                    setIsCancelling(false);
                    setIsResponding(false);
                    closeCurrentEventSource();
                    setCurrentTaskId(null);
                    cancelTimeoutRef.current = null;
                    setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
                }, 15000);
            } else {
                const errorData = await response.json().catch(() => ({ message: "Unknown cancellation error" }));
                throw new Error(errorData.message || `HTTP error ${response.status}`);
            }
        } catch (error) {
            setError({ title: "Task Cancellation Failed", error: getErrorMessage(error, "An unknown error occurred.") });
            setIsCancelling(false);
        }
    }, [isResponding, isCancelling, currentTaskId, addNotification, closeCurrentEventSource, setMessages, setError]);

    const handleFeedbackSubmit = useCallback(
        async (taskId: string, feedbackType: "up" | "down", feedbackText: string) => {
            if (!sessionId) {
                console.error("Cannot submit feedback without a session ID.");
                return;
            }
            try {
                await api.webui.post("/api/v1/feedback", {
                    taskId,
                    sessionId,
                    feedbackType,
                    feedbackText,
                });
                setSubmittedFeedback(prev => ({
                    ...prev,
                    [taskId]: { type: feedbackType, text: feedbackText },
                }));
            } catch (error) {
                console.error("Failed to submit feedback:", error);
                throw error;
            }
        },
        [sessionId]
    );

    const handleSseOpen = useCallback(() => {
        /* console.log for SSE open */
    }, []);

    const handleSseError = useCallback(() => {
        if (isResponding && !isFinalizing.current && !isCancellingRef.current) {
            setError({ title: "Connection Failed", error: "Connection lost. Please try again." });
        }
        if (!isFinalizing.current) {
            setIsResponding(false);
            if (!isCancellingRef.current) {
                closeCurrentEventSource();
                setCurrentTaskId(null);
            }
            latestStatusText.current = null;
        }
        setMessages(prev => prev.filter(msg => !msg.isStatusBubble).map((m, i, arr) => (i === arr.length - 1 && !m.isUser ? { ...m, isComplete: true } : m)));
    }, [closeCurrentEventSource, isResponding, setError, setMessages]);

    const cleanupUploadedFiles = useCallback(async (uploadedFiles: Array<{ filename: string; sessionId: string }>) => {
        if (uploadedFiles.length === 0) {
            return;
        }

        for (const { filename, sessionId: fileSessionId } of uploadedFiles) {
            try {
                // Use the session ID that was used during upload
                await api.webui.delete(`/api/v1/artifacts/${fileSessionId}/${encodeURIComponent(filename)}`);
            } catch (error) {
                console.error(`[cleanupUploadedFiles] Exception while cleaning up file ${filename}:`, error);
                // Continue cleanup even if one fails (intentionally silent)
            }
        }
    }, []);

    const handleSubmit = useCallback(
        async (event: FormEvent, files?: File[] | null, userInputText?: string | null, overrideSessionId?: string | null, displayHtml?: string | null, contextQuote?: string | null, contextQuoteSourceId?: string | null) => {
            event.preventDefault();
            const currentInput = userInputText?.trim() || "";
            const currentFiles = files || [];
            if ((!currentInput && currentFiles.length === 0) || isResponding || isCancelling || !selectedAgentName) {
                return;
            }
            closeCurrentEventSource();
            isFinalizing.current = false;
            setIsResponding(true);
            setCurrentTaskId(null);
            latestStatusText.current = null;

            sseEventSequenceRef.current = 0;

            const userMsg: MessageFE = {
                role: "user",
                parts: [{ kind: "text", text: currentInput }],
                isUser: true,
                uploadedFiles: currentFiles.length > 0 ? currentFiles : undefined,
                displayHtml: displayHtml || undefined,
                contextQuote: contextQuote || undefined,
                contextQuoteSourceId: contextQuoteSourceId || undefined,
                metadata: {
                    messageId: `msg-${v4()}`,
                    sessionId: overrideSessionId || sessionId,
                    lastProcessedEventSequence: 0,
                },
            };
            latestStatusText.current = "Thinking";
            setMessages(prev => [...prev, userMsg]);

            try {
                // 1. Process files using hybrid approach with fail-fast
                const uploadedFileParts: FilePart[] = [];
                const successfullyUploadedFiles: Array<{ filename: string; sessionId: string }> = []; // Track large files for cleanup

                // Track the effective session ID for this message (may be updated if large file upload)
                // Use overrideSessionId if provided (e.g., from artifact upload that created a session)
                let effectiveSessionId = overrideSessionId || sessionId;

                console.log(`[handleSubmit] Processing ${currentFiles.length} file(s)`);

                for (const file of currentFiles) {
                    // Check if this is an artifact reference (pasted artifact)
                    if (file.type === "application/x-artifact-reference") {
                        try {
                            // Read the artifact reference data
                            const text = await file.text();
                            const artifactRef = JSON.parse(text);

                            if (artifactRef.isArtifactReference && artifactRef.uri) {
                                // This is a pasted artifact - send it as a file part with URI
                                console.log(`[handleSubmit] Adding artifact reference: ${artifactRef.filename} (${artifactRef.uri})`);
                                uploadedFileParts.push({
                                    kind: "file",
                                    file: {
                                        uri: artifactRef.uri,
                                        name: artifactRef.filename,
                                        mimeType: artifactRef.mimeType || "application/octet-stream",
                                    },
                                });
                                continue; // Skip to next file
                            }
                        } catch (error) {
                            console.error(`[handleSubmit] Error processing artifact reference:`, error);
                            // Fall through to normal file handling
                        }
                    }

                    if (file.size < INLINE_FILE_SIZE_LIMIT_BYTES) {
                        // Small file: send inline as base64 (no cleanup needed)
                        const base64Content = await fileToBase64(file);
                        uploadedFileParts.push({
                            kind: "file",
                            file: {
                                bytes: base64Content,
                                name: file.name,
                                mimeType: file.type,
                            },
                        });
                    } else {
                        // Large file: upload and get URI, pass effectiveSessionId to ensure all files go to the same session
                        const result = await uploadArtifactFile(file, effectiveSessionId);

                        // Check for success FIRST - must have both uri and sessionId
                        if (result && "uri" in result && result.uri && result.sessionId) {
                            // Update effective session ID once if backend has created a new session
                            if (!effectiveSessionId) {
                                effectiveSessionId = result.sessionId;
                            }

                            successfullyUploadedFiles.push({
                                filename: file.name,
                                sessionId: result.sessionId,
                            });

                            uploadedFileParts.push({
                                kind: "file",
                                file: {
                                    uri: result.uri,
                                    name: file.name,
                                    mimeType: file.type,
                                },
                            });
                        } else {
                            // ANY failure case (error object, null, or missing fields) - Clean up and stop
                            console.error(`[handleSubmit] File upload failed for "${file.name}". Result:`, result);
                            await cleanupUploadedFiles(successfullyUploadedFiles);

                            const cleanupMessage = successfullyUploadedFiles.length > 0 ? " Previously uploaded files have been cleaned up." : "";

                            const errorDetail = result && "error" in result ? ` (${result.error})` : "";
                            setError({ title: "File Upload Failed", error: `Message not sent. File upload failed for "${file.name}"${errorDetail}.${cleanupMessage}.` });
                            setIsResponding(false);
                            setMessages(prev => prev.filter(msg => msg.metadata?.messageId !== userMsg.metadata?.messageId));
                            return;
                        }
                    }
                }

                // 2. Construct message parts
                const messageParts: Part[] = [];
                if (currentInput) {
                    messageParts.push({ kind: "text", text: currentInput });
                }

                messageParts.push(...uploadedFileParts);

                if (messageParts.length === 0) {
                    return;
                }

                // 3. Construct the A2A message
                console.log(`ChatProvider handleSubmit: Using effectiveSessionId for contextId: ${effectiveSessionId}`);

                // Check if background execution is enabled via gateway config
                const enableBackgroundExecution = backgroundTasksEnabled ?? false;
                console.log(`[ChatProvider] Building metadata for ${selectedAgentName}, enableBackground=${enableBackgroundExecution}`);

                // Build metadata object
                const messageMetadata: Record<string, any> = {
                    agent_name: selectedAgentName,
                };

                if (activeProject?.id) {
                    messageMetadata.project_id = activeProject.id;
                }

                if (enableBackgroundExecution) {
                    messageMetadata.backgroundExecutionEnabled = true;
                    messageMetadata.maxExecutionTimeMs = backgroundTasksDefaultTimeoutMs ?? 3600000; // Default 1 hour
                    console.log(`[ChatProvider] Enabling background execution for ${selectedAgentName}`);
                    console.log(`[ChatProvider] Metadata object:`, messageMetadata);
                }

                const a2aMessage: Message = {
                    role: "user",
                    parts: messageParts,
                    messageId: `msg-${v4()}`,
                    kind: "message",
                    contextId: effectiveSessionId,
                    metadata: messageMetadata,
                };

                console.log(`[ChatProvider] A2A message metadata:`, a2aMessage.metadata);

                // 4. Construct the SendStreamingMessageRequest
                const sendMessageRequest: SendStreamingMessageRequest = {
                    jsonrpc: "2.0",
                    id: `req-${v4()}`,
                    method: "message/stream",
                    params: {
                        message: a2aMessage,
                    },
                };

                // 5. Send the request
                console.log("ChatProvider handleSubmit: Sending POST to /message:stream");
                const result: SendStreamingMessageSuccessResponse = await api.webui.post("/api/v1/message:stream", sendMessageRequest);

                const task = result?.result as Task | undefined;
                const taskId = task?.id;
                const responseSessionId = (task as Task & { contextId?: string })?.contextId;

                console.log(`ChatProvider handleSubmit: Extracted responseSessionId: ${responseSessionId}, current sessionId: ${sessionId}`);
                console.log(`ChatProvider handleSubmit: Full result object:`, result);

                if (!taskId) {
                    console.error("ChatProvider handleSubmit: Backend did not return a valid taskId. Result:", result);
                    throw new Error("Backend did not return a valid taskId.");
                }

                // Update session ID if backend provided one (for new sessions)
                console.log(`ChatProvider handleSubmit: Checking session update condition - responseSessionId: ${responseSessionId}, sessionId: ${sessionId}, different: ${responseSessionId !== sessionId}`);
                const isNewSession = !sessionId || sessionId === "";
                const finalSessionId = responseSessionId || sessionId;

                if (responseSessionId && responseSessionId !== sessionId) {
                    console.log(`ChatProvider handleSubmit: Updating sessionId from ${sessionId} to ${responseSessionId}`);
                    setSessionId(responseSessionId);
                    // Update the user message metadata with the new session ID
                    setMessages(prev => prev.map(msg => (msg.metadata?.messageId === userMsg.metadata?.messageId ? { ...msg, metadata: { ...msg.metadata, sessionId: responseSessionId } } : msg)));

                    // If it was a new session, generate and persist its name
                    if (isNewSession) {
                        let newSessionName = "New Chat";

                        // When auto title generation is DISABLED, use the user's message as the session name
                        // When auto title generation is ENABLED, keep "New Chat" as placeholder - LLM will generate the title
                        if (!autoTitleGenerationEnabled) {
                            const textParts = userMsg.parts.filter(p => p.kind === "text") as TextPart[];
                            const combinedText = textParts
                                .map(p => p.text)
                                .join(" ")
                                .trim();

                            if (combinedText) {
                                // Convert internal mention format @[Name](id) to display format @Name
                                // Also strip backend mention format <user_id:...> from the text
                                // The regex handles both complete (<user_id:id>) and truncated (<user_id:id) cases
                                let displayText = internalToDisplayText(combinedText);
                                displayText = displayText.replace(/<user_id:[^>]*>?/g, "").trim();
                                newSessionName = displayText.length > 100 ? `${displayText.substring(0, 100)}...` : displayText;
                            } else if (currentFiles.length > 0) {
                                // No text, but files were sent - derive name from files
                                if (currentFiles.length === 1) {
                                    newSessionName = currentFiles[0].name;
                                } else {
                                    newSessionName = `${currentFiles[0].name} +${currentFiles.length - 1} more`;
                                }
                            }
                        }

                        if (newSessionName) {
                            setSessionName(newSessionName);
                            await updateSessionName(responseSessionId, newSessionName);
                        }
                    }

                    // Trigger session list refresh for new sessions
                    if (isNewSession && typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                }

                // Save initial task with user message
                // For background tasks, we save with "pending" status so the session list shows the spinner
                // The backend TaskLoggerService will update this with the full response when complete
                const enabledForBackground = backgroundTasksEnabled ?? false;
                if (finalSessionId) {
                    await saveTaskToBackend(
                        {
                            task_id: taskId,
                            user_message: currentInput,
                            message_bubbles: [serializeChatMessage(userMsg)],
                            task_metadata: {
                                schema_version: CURRENT_SCHEMA_VERSION,
                                status: "pending",
                                agent_name: selectedAgentName,
                                is_background_task: enabledForBackground,
                            },
                        },
                        finalSessionId
                    ); // Pass session ID explicitly
                }

                console.log(`ChatProvider handleSubmit: Received taskId ${taskId}. Setting currentTaskId and taskIdInSidePanel.`);
                setCurrentTaskId(taskId);
                setTaskIdInSidePanel(taskId);

                // Pre-register the task in the task monitor so it's available for visualization immediately
                // This prevents race conditions where the side panel tries to visualize before SSE events arrive
                const textParts = userMsg.parts.filter(p => p.kind === "text") as TextPart[];
                const initialRequestText =
                    textParts
                        .map(p => p.text)
                        .join(" ")
                        .trim() || "Task started...";
                registerTaskEarly(taskId, initialRequestText);

                // Check if this should be a background task (enabled via gateway config)
                if (enabledForBackground) {
                    console.log(`[ChatProvider] Registering ${taskId} as background task`);
                    registerBackgroundTask(taskId, finalSessionId, selectedAgentName);

                    // Trigger session list refresh to show spinner immediately
                    if (typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                }

                // Update user message with taskId so it's included in final save
                setMessages(prev => prev.map(msg => (msg.metadata?.messageId === userMsg.metadata?.messageId ? { ...msg, taskId: taskId } : msg)));
            } catch (error) {
                setError({ title: "Message Failed", error: getErrorMessage(error, "An error occurred. Please try again.") });
                setIsResponding(false);
                setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
                setCurrentTaskId(null);
                isFinalizing.current = false;
                latestStatusText.current = null;
            }
        },
        [
            isResponding,
            isCancelling,
            selectedAgentName,
            closeCurrentEventSource,
            sessionId,
            setMessages,
            backgroundTasksEnabled,
            activeProject?.id,
            registerTaskEarly,
            uploadArtifactFile,
            cleanupUploadedFiles,
            setError,
            backgroundTasksDefaultTimeoutMs,
            autoTitleGenerationEnabled,
            updateSessionName,
            saveTaskToBackend,
            registerBackgroundTask,
        ]
    );

    const prevProjectIdRef = useRef<string | null | undefined>("");
    const isSessionSwitchRef = useRef(false);
    const isSessionMoveRef = useRef(false);

    useEffect(() => {
        const handleProjectDeleted = (deletedProjectId: string) => {
            if (activeProject?.id === deletedProjectId) {
                console.log(`Project ${deletedProjectId} was deleted, clearing session context`);
                handleNewSession(false);
            }
        };

        registerProjectDeletedCallback(handleProjectDeleted);
    }, [activeProject, handleNewSession]);

    useEffect(() => {
        const handleTitleUpdated = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { sessionId: updatedSessionId } = customEvent.detail;

            // If the updated session is the current session, fetch and update the name
            if (updatedSessionId === sessionId) {
                try {
                    const sessionData = await api.webui.get(`/api/v1/sessions/${updatedSessionId}`);
                    const updatedSession = sessionData?.data;
                    if (updatedSession?.name) {
                        setSessionName(updatedSession.name);
                    }
                } catch (error) {
                    console.error("[ChatProvider] Error fetching updated session name:", error);
                }
            }
        };

        window.addEventListener("session-title-updated", handleTitleUpdated);
        return () => {
            window.removeEventListener("session-title-updated", handleTitleUpdated);
        };
    }, [sessionId]);

    // Listen for switch-to-session events (e.g., after forking a shared chat)
    useEffect(() => {
        const handleSwitchToSession = (event: Event) => {
            const detail = (event as CustomEvent).detail;
            if (detail?.sessionId) {
                handleSwitchSession(detail.sessionId);
            }
        };
        window.addEventListener("switch-to-session", handleSwitchToSession);
        return () => {
            window.removeEventListener("switch-to-session", handleSwitchToSession);
        };
    }, [handleSwitchSession]);

    useEffect(() => {
        const handleSessionUpdated = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { sessionId: updatedSessionId, projectId } = customEvent.detail;

            // Only handle if projectId is present (indicating a move)
            if (projectId === undefined) return;

            // If the updated session is the current session, update the project context
            if (updatedSessionId === sessionId) {
                // Set flag to prevent handleNewSession from being triggered by this project change
                isSessionMoveRef.current = true;

                if (projectId) {
                    // Session moved to a project - activate that project
                    const project = projects.find((p: Project) => p.id === projectId);
                    if (project) {
                        setActiveProject(project);
                    }
                } else {
                    // Session moved out of project - deactivate project context
                    setActiveProject(null);
                }
            }
        };

        window.addEventListener("session-updated", handleSessionUpdated);
        return () => {
            window.removeEventListener("session-updated", handleSessionUpdated);
        };
    }, [sessionId, projects, setActiveProject]);

    useEffect(() => {
        // Listen for background task completion events
        // When a background task completes, reload the session if it's currently active
        // If the user is on a different session, the buffer stays until they switch back
        // (buffer cleanup happens after replay + save)
        const handleBackgroundTaskCompleted = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { taskId: completedTaskId } = customEvent.detail;

            // Find the completed task
            const completedTask = backgroundTasksRef.current.find(t => t.taskId === completedTaskId);
            if (completedTask) {
                console.log(`[ChatProvider] Background task ${completedTaskId} completed for session ${completedTask.sessionId}`);

                // Only replay if the user is currently viewing the session where the task completed
                if (currentSessionIdRef.current === completedTask.sessionId) {
                    console.log(`[ChatProvider] User is on same session - will replay buffered events after delay`);
                    // Wait a bit to ensure any pending operations complete
                    setTimeout(async () => {
                        // Try to replay buffered events first (new single-path approach)
                        // This ensures embeds and templates are properly resolved through the frontend's SSE processing
                        const replayedSuccessfully = await replayBufferedEvents(completedTaskId);

                        if (!replayedSuccessfully) {
                            // Fall back to loading from chat_tasks if no buffered events
                            console.log(`[ChatProvider] No buffered events, falling back to loadSessionTasks`);
                            await loadSessionTasks(completedTask.sessionId);
                        }
                    }, 1500); // Delay to ensure save completes
                } else {
                    // User is on a different session - buffer stays until they switch back to that session
                    // When they switch back, handleSwitchSession will detect buffered events and replay them
                    console.log(`[ChatProvider] User is on different session (${currentSessionIdRef.current}) - buffer preserved for later replay when they switch back to ${completedTask.sessionId}`);
                }
            }
        };

        window.addEventListener("background-task-completed", handleBackgroundTaskCompleted);
        return () => {
            window.removeEventListener("background-task-completed", handleBackgroundTaskCompleted);
        };
    }, [loadSessionTasks, replayBufferedEvents]);

    useEffect(() => {
        // When the active project changes, reset the chat view to a clean slate
        // UNLESS the change was triggered by switching to a session (which handles its own state)
        // OR by moving a session (which should not start a new session)
        // Only trigger when activating or switching projects, not when deactivating (going to null)
        const prevId = prevProjectIdRef.current;
        const currentId = activeProject?.id;
        const isActivatingOrSwitching = currentId !== undefined && prevId !== currentId;

        if (isActivatingOrSwitching && !isSessionSwitchRef.current && !isSessionMoveRef.current) {
            console.log("Active project changed explicitly, resetting chat view and preserving project context.");
            handleNewSession(true); // Preserve the project context when switching projects
        }
        prevProjectIdRef.current = currentId;
        // Reset the flags after processing
        isSessionSwitchRef.current = false;
        isSessionMoveRef.current = false;
    }, [activeProject, handleNewSession]);

    useEffect(() => {
        // Don't show welcome message if we're loading a session
        if (!selectedAgentName && agents.length > 0 && messages.length === 0 && !isLoadingSession) {
            // Priority order for agent selection:
            // 1. URL parameter agent (?agent=AgentName)
            // 2. Project's default agent (if in project context)
            // 3. OrchestratorAgent (fallback)
            // 4. First available agent
            let selectedAgent = agents[0];

            // Check URL parameter first
            const urlParams = new URLSearchParams(window.location.search);
            const urlAgentName = urlParams.get("agent");
            let urlAgent: AgentCardInfo | undefined;

            if (urlAgentName) {
                urlAgent = agents.find(agent => agent.name === urlAgentName);
                if (urlAgent) {
                    selectedAgent = urlAgent;
                    console.log(`Using URL parameter agent: ${selectedAgent.name}`);
                } else {
                    console.warn(`URL parameter agent "${urlAgentName}" not found in available agents, falling back to priority order`);
                }
            }

            // If no URL agent found, follow existing priority order
            if (!urlAgent) {
                if (activeProject?.defaultAgentId) {
                    const projectDefaultAgent = agents.find(agent => agent.name === activeProject.defaultAgentId);
                    if (projectDefaultAgent) {
                        selectedAgent = projectDefaultAgent;
                        console.log(`Using project default agent: ${selectedAgent.name}`);
                    } else {
                        console.warn(`Project default agent "${activeProject.defaultAgentId}" not found, falling back to OrchestratorAgent`);
                        selectedAgent = agents.find(agent => agent.name === "OrchestratorAgent") ?? agents[0];
                    }
                } else {
                    selectedAgent = agents.find(agent => agent.name === "OrchestratorAgent") ?? agents[0];
                }
            }

            setSelectedAgentName(selectedAgent.name);

            const displayedText = configWelcomeMessage || `Hi! I'm the ${selectedAgent?.displayName}. How can I help?`;
            setMessages([
                {
                    parts: [{ kind: "text", text: displayedText }],
                    isUser: false,
                    isComplete: true,
                    role: "agent",
                    metadata: {
                        sessionId: "",
                        lastProcessedEventSequence: 0,
                    },
                },
            ]);
        }
    }, [agents, configWelcomeMessage, messages.length, selectedAgentName, sessionId, isLoadingSession, activeProject, setMessages]);

    // Store the latest handlers in refs so they can be accessed without triggering effect re-runs
    // Note: handleSseMessageRef is declared earlier (line ~103) for use in loadSessionTasks
    const handleSseOpenRef = useRef(handleSseOpen);
    const handleSseErrorRef = useRef(handleSseError);

    // Update refs whenever handlers change (but this won't trigger the effect)
    useEffect(() => {
        handleSseMessageRef.current = handleSseMessage;
        handleSseOpenRef.current = handleSseOpen;
        handleSseErrorRef.current = handleSseError;
    }, [handleSseMessage, handleSseOpen, handleSseError]);

    useEffect(() => {
        if (currentTaskId) {
            const bearerToken = getApiBearerToken();

            const bgTask = backgroundTasksRef.current.find(t => t.taskId === currentTaskId);
            const isReconnecting = bgTask !== undefined;

            const params = new URLSearchParams();
            if (bearerToken) {
                params.append("token", bearerToken);
            }

            if (isReconnecting) {
                params.append("reconnect", "true");
                params.append("last_event_timestamp", "0");
                console.log(`[ChatProvider] Reconnecting to background task ${currentTaskId} - requesting full event replay`);

                setMessages(prev => {
                    const filtered = prev.filter(msg => {
                        if (msg.isUser) return true;
                        if (msg.taskId !== currentTaskId) return true;
                        return false;
                    });
                    return filtered;
                });
            }

            const baseUrl = api.webui.getFullUrl(`/api/v1/sse/subscribe/${currentTaskId}`);
            const eventSourceUrl = params.toString() ? `${baseUrl}?${params.toString()}` : baseUrl;
            const eventSource = new EventSource(eventSourceUrl, { withCredentials: true });
            currentEventSource.current = eventSource;

            const wrappedHandleSseOpen = () => {
                handleSseOpenRef.current();
            };

            const wrappedHandleSseError = () => {
                handleSseErrorRef.current();
            };

            const wrappedHandleSseMessage = (event: MessageEvent) => {
                if (handleSseMessageRef.current) {
                    handleSseMessageRef.current(event);
                }
            };

            eventSource.onopen = wrappedHandleSseOpen;
            eventSource.onerror = wrappedHandleSseError;
            eventSource.addEventListener("status_update", wrappedHandleSseMessage);
            eventSource.addEventListener("artifact_update", wrappedHandleSseMessage);
            eventSource.addEventListener("final_response", wrappedHandleSseMessage);
            eventSource.addEventListener("error", wrappedHandleSseMessage);

            return () => {
                // Explicitly remove listeners before closing
                eventSource.removeEventListener("status_update", wrappedHandleSseMessage);
                eventSource.removeEventListener("artifact_update", wrappedHandleSseMessage);
                eventSource.removeEventListener("final_response", wrappedHandleSseMessage);
                eventSource.removeEventListener("error", wrappedHandleSseMessage);
                eventSource.close();
            };
        } else {
            closeCurrentEventSource();
        }
    }, [currentTaskId, closeCurrentEventSource, setMessages]);

    const contextValue: ChatContextValue = {
        ragData,
        ragEnabled,
        expandedDocumentFilename,
        setExpandedDocumentFilename,
        configCollectFeedback,
        submittedFeedback,
        handleFeedbackSubmit,
        sessionId,
        setSessionId,
        sessionName,
        setSessionName,
        messages,
        setMessages,
        isResponding,
        isCollaborativeSession,
        hasSharedEditors,
        currentUserEmail,
        sessionOwnerName,
        sessionOwnerEmail,
        currentTaskId,
        isCancelling,
        latestStatusText,
        isLoadingSession,
        agents,
        agentsLoading,
        agentsError,
        agentsRefetch,
        agentNameDisplayNameMap,
        handleNewSession,
        handleSwitchSession,
        handleSubmit,
        handleCancel,
        notifications,
        addNotification,
        selectedAgentName,
        setSelectedAgentName,
        artifacts,
        allArtifacts,
        artifactsLoading,
        artifactsRefetch,
        setArtifacts,
        showWorkingArtifacts,
        toggleShowWorkingArtifacts,
        workingArtifactCount,
        uploadArtifactFile,
        isSidePanelCollapsed,
        activeSidePanelTab,
        setIsSidePanelCollapsed,
        setActiveSidePanelTab,
        openSidePanelTab,
        taskIdInSidePanel,
        setTaskIdInSidePanel,
        isDeleteModalOpen,
        artifactToDelete,
        openDeleteModal,
        closeDeleteModal,
        confirmDelete,
        openSessionDeleteModal,
        closeSessionDeleteModal,
        confirmSessionDelete,
        sessionToDelete,
        isArtifactEditMode,
        setIsArtifactEditMode,
        selectedArtifactFilenames,
        setSelectedArtifactFilenames,
        handleDeleteSelectedArtifacts,
        confirmBatchDeleteArtifacts,
        isBatchDeleteModalOpen,
        setIsBatchDeleteModalOpen,
        previewedArtifactAvailableVersions,
        currentPreviewedVersionNumber,
        previewFileContent,
        openArtifactForPreview: openPreview,
        navigateArtifactVersion: navigateToVersion,
        previewArtifact,
        setPreviewArtifact: setPreviewByArtifact,
        updateSessionName,
        deleteSession,

        /** Artifact Display and Cache Management */
        markArtifactAsDisplayed,
        downloadAndResolveArtifact,

        /** Global error display */
        displayError: setError,

        /** Pending prompt for starting new chat */
        pendingPrompt,
        startNewChatWithPrompt,
        clearPendingPrompt,

        /** Background Task Monitoring */
        backgroundTasks,
        backgroundNotifications,
        isTaskRunningInBackground,

        hasModelConfigWrite: !configUseAuthorization,
    };

    // Handlers for the running task warning dialog
    const handleConfirmNavigation = useCallback(() => {
        setRunningTaskWarningOpen(false);
        if (pendingNavigationAction) {
            pendingNavigationAction();
            setPendingNavigationAction(null);
        }
    }, [pendingNavigationAction]);

    const handleCancelNavigation = useCallback(() => {
        setRunningTaskWarningOpen(false);
        setPendingNavigationAction(null);
    }, []);

    return (
        <ChatContext.Provider value={contextValue}>
            {children}
            <ErrorDialog />
            {/* Warning dialog when user tries to navigate away while a task is running and background tasks are disabled */}
            <ConfirmationDialog
                open={runningTaskWarningOpen}
                title="Task in Progress"
                description="A task is currently running. If you navigate away now, you may lose the response. Are you sure you want to leave?"
                onOpenChange={setRunningTaskWarningOpen}
                onConfirm={handleConfirmNavigation}
                onCancel={handleCancelNavigation}
                actionLabels={{
                    cancel: "Stay",
                    confirm: "Leave Anyway",
                }}
            />
        </ChatContext.Provider>
    );
};
