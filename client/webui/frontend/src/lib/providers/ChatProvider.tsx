/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useCallback, useEffect, useRef, type FormEvent, type ReactNode } from "react";
import { v4 } from "uuid";

import { api } from "@/lib/api";
import { ChatContext, type ChatContextValue, type PendingPromptData } from "@/lib/contexts";
import { useConfigContext, useArtifacts, useAgentCards, useErrorDialog, useBackgroundTaskMonitor, useArtifactPreview, useArtifactOperations } from "@/lib/hooks";
import { useProjectContext, registerProjectDeletedCallback } from "@/lib/providers";
import { getAccessToken, getErrorMessage, fileToBase64, migrateTask, CURRENT_SCHEMA_VERSION } from "@/lib/utils";

import type {
    CancelTaskRequest,
    DataPart,
    FileAttachment,
    FilePart,
    JSONRPCErrorResponse,
    Message,
    MessageFE,
    Notification,
    Part,
    PartFE,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Session,
    Task,
    TaskStatusUpdateEvent,
    TextPart,
    ArtifactPart,
    AgentCardInfo,
    Project,
    StoredTaskData,
} from "@/lib/types";

const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, persistenceEnabled, configCollectFeedback, backgroundTasksEnabled, backgroundTasksDefaultTimeoutMs } = useConfigContext();
    const { activeProject, setActiveProject, projects } = useProjectContext();
    const { ErrorDialog, setError } = useErrorDialog();

    // State Variables from useChat
    const [sessionId, setSessionId] = useState<string>("");
    const [messages, setMessages] = useState<MessageFE[]>([]);
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const currentEventSource = useRef<EventSource | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false); // New state for cancellation

    const savingTasksRef = useRef<Set<string>>(new Set());

    // Track isCancelling in ref to access in async callbacks
    const isCancellingRef = useRef(isCancelling);
    useEffect(() => {
        isCancellingRef.current = isCancelling;
    }, [isCancelling]);

    // Track current session id to prevent race conditions
    const currentSessionIdRef = useRef(sessionId);
    useEffect(() => {
        currentSessionIdRef.current = sessionId;
    }, [sessionId]);

    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);
    const backgroundTasksRef = useRef<typeof backgroundTasks>([]);
    const messagesRef = useRef<MessageFE[]>([]);

    // Agents State
    const { agents, agentNameMap: agentNameDisplayNameMap, error: agentsError, isLoading: agentsLoading, refetch: agentsRefetch } = useAgentCards();

    // Chat Side Panel State
    const { artifacts, isLoading: artifactsLoading, refetch: artifactsRefetch, setArtifacts } = useArtifacts(sessionId);

    // Side Panel Control State
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState<boolean>(true);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "workflow">("files");

    // Feedback State
    const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, { type: "up" | "down"; text: string }>>({});

    // Pending prompt state for starting new chat with a prompt template
    const [pendingPrompt, setPendingPrompt] = useState<PendingPromptData | null>(null);

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
        artifacts,
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

    const {
        backgroundTasks,
        notifications: backgroundNotifications,
        registerBackgroundTask,
        unregisterBackgroundTask,
        updateTaskTimestamp,
        isTaskRunningInBackground,
        checkTaskStatus,
    } = useBackgroundTaskMonitor({
        userId: "sam_dev_user",
        currentSessionId: sessionId,
        onTaskCompleted: useCallback(
            (taskId: string) => {
                addNotification("Background task completed", "success");

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
            [addNotification]
        ),
        onTaskFailed: useCallback(
            (taskId: string, error: string) => {
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

    // Keep refs in sync with state
    useEffect(() => {
        backgroundTasksRef.current = backgroundTasks;
    }, [backgroundTasks]);

    useEffect(() => {
        messagesRef.current = messages;
    }, [messages]);

    // Helper function to serialize a MessageFE to MessageBubble format for backend
    const serializeMessageBubble = useCallback((message: MessageFE) => {
        // Build text with artifact markers embedded
        let combinedText = "";
        const parts = message.parts || [];

        for (const part of parts) {
            if (part.kind === "text") {
                combinedText += (part as TextPart).text;
            } else if (part.kind === "artifact") {
                // Add artifact marker for artifact parts
                const artifactPart = part as ArtifactPart;
                combinedText += `«artifact_return:${artifactPart.name}»`;
            }
        }

        return {
            id: message.metadata?.messageId || `msg-${v4()}`,
            type: message.isUser ? "user" : "agent",
            text: combinedText,
            parts: message.parts,
            uploadedFiles: message.uploadedFiles?.map(f => ({
                name: f.name,
                type: f.type,
            })),
            isError: message.isError,
        };
    }, []);

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

    // Helper function to extract artifact markers and create artifact parts
    const extractArtifactMarkers = useCallback((text: string, sessionId: string, addedArtifacts: Set<string>, processedParts: any[]) => {
        const ARTIFACT_RETURN_REGEX = /«artifact_return:([^»]+)»/g;
        const ARTIFACT_REGEX = /«artifact:([^»]+)»/g;

        const createArtifactPart = (filename: string) => ({
            kind: "artifact",
            status: "completed",
            name: filename,
            file: {
                name: filename,
                uri: `artifact://${sessionId}/${filename}`,
            },
        });

        // Extract artifact_return markers
        let match;
        while ((match = ARTIFACT_RETURN_REGEX.exec(text)) !== null) {
            const artifactFilename = match[1];
            if (!addedArtifacts.has(artifactFilename)) {
                addedArtifacts.add(artifactFilename);
                processedParts.push(createArtifactPart(artifactFilename));
            }
        }

        // Extract artifact: markers
        while ((match = ARTIFACT_REGEX.exec(text)) !== null) {
            const artifactFilename = match[1];
            if (!addedArtifacts.has(artifactFilename)) {
                addedArtifacts.add(artifactFilename);
                processedParts.push(createArtifactPart(artifactFilename));
            }
        }
    }, []);

    // Helper function to deserialize task data to MessageFE objects
    const deserializeTaskToMessages = useCallback(
        (task: { taskId: string; messageBubbles: any[]; taskMetadata?: any; createdTime: number }, sessionId: string): MessageFE[] => {
            return task.messageBubbles.map(bubble => {
                // Process parts to handle markers and reconstruct artifact parts if needed
                const processedParts: any[] = [];
                const originalParts = bubble.parts || [{ kind: "text", text: bubble.text || "" }];

                // Track artifact names we've already added to avoid duplicates
                const addedArtifacts = new Set<string>();

                // First, check the bubble.text field for artifact markers (TaskLoggerService saves markers there)
                // This handles the case where backend saves text with markers but parts without artifacts
                if (bubble.text) {
                    extractArtifactMarkers(bubble.text, sessionId, addedArtifacts, processedParts);
                }

                for (const part of originalParts) {
                    if (part.kind === "text" && part.text) {
                        let textContent = part.text;

                        // Extract artifact markers and convert them to artifact parts
                        extractArtifactMarkers(textContent, sessionId, addedArtifacts, processedParts);

                        // Remove artifact markers from text content
                        textContent = textContent.replace(/«artifact_return:[^»]+»/g, "");
                        textContent = textContent.replace(/«artifact:[^»]+»/g, "");

                        // Remove status update markers
                        textContent = textContent.replace(/«status_update:[^»]+»\n?/g, "");

                        // Add text part if there's content
                        if (textContent.trim()) {
                            processedParts.push({ kind: "text", text: textContent });
                        }
                    } else if (part.kind === "artifact") {
                        // Only add artifact part if not already added (from markers)
                        const artifactName = part.name;
                        if (artifactName && !addedArtifacts.has(artifactName)) {
                            addedArtifacts.add(artifactName);
                            processedParts.push(part);
                        }
                        // Skip duplicate artifacts
                    } else {
                        // Keep other non-text parts as-is
                        processedParts.push(part);
                    }
                }

                return {
                    taskId: task.taskId,
                    role: bubble.type === "user" ? "user" : "agent",
                    parts: processedParts,
                    isUser: bubble.type === "user",
                    isComplete: true,
                    files: bubble.files,
                    uploadedFiles: bubble.uploadedFiles,
                    artifactNotification: bubble.artifactNotification,
                    isError: bubble.isError,
                    metadata: {
                        messageId: bubble.id,
                        sessionId: sessionId,
                        lastProcessedEventSequence: 0,
                    },
                };
            });
        },
        [extractArtifactMarkers]
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
            for (const task of migratedTasks) {
                const taskMessages = deserializeTaskToMessages(task, sessionId);
                allMessages.push(...taskMessages);
            }

            // Extract feedback state from task metadata
            const feedbackMap: Record<string, { type: "up" | "down"; text: string }> = {};
            for (const task of migratedTasks) {
                if (task.taskMetadata?.feedback) {
                    feedbackMap[task.taskId] = {
                        type: task.taskMetadata.feedback.type,
                        text: task.taskMetadata.feedback.text || "",
                    };
                }
            }

            // Extract agent name from the most recent task
            // (Use the last task's agent since that's the most recent interaction)
            let agentName: string | null = null;
            for (let i = migratedTasks.length - 1; i >= 0; i--) {
                if (migratedTasks[i].taskMetadata?.agent_name) {
                    agentName = migratedTasks[i].taskMetadata.agent_name;
                    break;
                }
            }

            // Update state
            setMessages(allMessages);
            setSubmittedFeedback(feedbackMap);

            // Set the agent name if found
            if (agentName) {
                setSelectedAgentName(agentName);
            }

            // Set taskIdInSidePanel to the most recent task for workflow visualization
            if (migratedTasks.length > 0) {
                const mostRecentTask = migratedTasks[migratedTasks.length - 1];
                setTaskIdInSidePanel(mostRecentTask.taskId);
            }
        },
        [deserializeTaskToMessages]
    );

    // Session State
    const [sessionName, setSessionName] = useState<string | null>(null);
    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);
    const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);

    const openSidePanelTab = useCallback((tab: "files" | "workflow") => {
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

    const handleSseMessage = useCallback(
        (event: MessageEvent) => {
            sseEventSequenceRef.current += 1;
            const currentEventSequence = sseEventSequenceRef.current;
            let rpcResponse: SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;

            try {
                rpcResponse = JSON.parse(event.data) as SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;
            } catch (error: unknown) {
                console.error("Failed to parse SSE message:", error);
                return;
            }

            // Update background task timestamp if this is a background task
            if ("result" in rpcResponse && rpcResponse.result) {
                const result = rpcResponse.result;
                const taskIdFromResult = result.kind === "task" ? result.id : result.kind === "status-update" ? result.taskId : undefined;

                if (taskIdFromResult && isTaskRunningInBackground(taskIdFromResult)) {
                    updateTaskTimestamp(taskIdFromResult, Date.now());
                }
            }

            // Handle RPC Error
            if ("error" in rpcResponse && rpcResponse.error) {
                const errorContent = rpcResponse.error;
                const messageContent = `Error: ${errorContent.message}`;

                setMessages(prev => {
                    const newMessages = prev.filter(msg => !msg.isStatusBubble);
                    newMessages.push({
                        role: "agent",
                        parts: [{ kind: "text", text: messageContent }],
                        isUser: false,
                        isError: true,
                        isComplete: true,
                        metadata: {
                            messageId: `msg-${v4()}`,
                            lastProcessedEventSequence: currentEventSequence,
                        },
                    });
                    return newMessages;
                });

                setIsResponding(false);
                closeCurrentEventSource();
                setCurrentTaskId(null);
                return;
            }

            if (!("result" in rpcResponse) || !rpcResponse.result) {
                console.warn("Received SSE message without a result or error field.", rpcResponse);
                return;
            }

            const result = rpcResponse.result;
            let isFinalEvent = false;
            let messageToProcess: Message | undefined;
            let currentTaskIdFromResult: string | undefined;

            // Determine event type and extract relevant data
            switch (result.kind) {
                case "task":
                    isFinalEvent = true;
                    // For the final task object, we only use it as a signal to end the turn.
                    // The content has already been streamed via status_updates.
                    messageToProcess = undefined;
                    currentTaskIdFromResult = result.id;
                    break;
                case "status-update":
                    isFinalEvent = result.final;
                    messageToProcess = result.status?.message;
                    currentTaskIdFromResult = result.taskId;
                    break;
                case "artifact-update":
                    // An artifact was created or updated, refetch the list for the side panel.
                    void artifactsRefetch();
                    return; // No further processing needed for this event.
                default:
                    console.warn("Received unknown result kind in SSE message:", result);
                    return;
            }

            // Process data parts first to extract status text
            if (messageToProcess?.parts) {
                const dataParts = messageToProcess.parts.filter(p => p.kind === "data") as DataPart[];
                if (dataParts.length > 0) {
                    for (const part of dataParts) {
                        const data = part.data as any;
                        if (data && typeof data === "object" && "type" in data) {
                            switch (data.type) {
                                case "agent_progress_update": {
                                    latestStatusText.current = String(data?.status_text ?? "Processing...");
                                    const otherParts = messageToProcess.parts.filter(p => p.kind !== "data");
                                    if (otherParts.length === 0) {
                                        return; // This is a status-only event, do not process further.
                                    }
                                    break;
                                }
                                case "artifact_creation_progress": {
                                    const { filename, status, bytes_transferred, mime_type, description, artifact_chunk, version } = data as {
                                        filename: string;
                                        status: "in-progress" | "completed" | "failed";
                                        bytes_transferred: number;
                                        mime_type?: string;
                                        description?: string;
                                        artifact_chunk?: string;
                                        version?: number;
                                    };

                                    // Track if we need to trigger auto-download after state update
                                    let shouldAutoDownload = false;

                                    // Update global artifacts list with description and accumulated content
                                    setArtifacts(prevArtifacts => {
                                        const existingIndex = prevArtifacts.findIndex(a => a.filename === filename);
                                        if (existingIndex >= 0) {
                                            // Update existing artifact, preserving description if new one not provided
                                            const updated = [...prevArtifacts];
                                            const existingArtifact = updated[existingIndex];
                                            const isDisplayed = existingArtifact.isDisplayed || false;

                                            // Check if we should trigger auto-download (before state update)
                                            if (status === "completed" && isDisplayed) {
                                                shouldAutoDownload = true;
                                            }

                                            updated[existingIndex] = {
                                                ...existingArtifact,
                                                description: description !== undefined ? description : existingArtifact.description,
                                                size: bytes_transferred || existingArtifact.size,
                                                last_modified: new Date().toISOString(),
                                                // Ensure URI is set
                                                uri: existingArtifact.uri || `artifact://${sessionId}/${filename}`,
                                                // Accumulate content chunks for in-progress and completed artifacts
                                                accumulatedContent:
                                                    status === "in-progress" && artifact_chunk
                                                        ? (existingArtifact.accumulatedContent || "") + artifact_chunk
                                                        : status === "completed" && !isDisplayed
                                                          ? undefined // Clear accumulated content when completed if NOT displayed
                                                          : existingArtifact.accumulatedContent, // Keep for displayed artifacts
                                                // Mark that streaming content is plain text (not base64)
                                                isAccumulatedContentPlainText: status === "in-progress" && artifact_chunk ? true : existingArtifact.isAccumulatedContentPlainText,
                                                // Update mime_type when completed
                                                mime_type: status === "completed" && mime_type ? mime_type : existingArtifact.mime_type,
                                                // Mark that embed resolution is needed when completed
                                                needsEmbedResolution: status === "completed" ? true : existingArtifact.needsEmbedResolution,
                                            };

                                            return updated;
                                        } else {
                                            // Create new artifact entry only if we have description or it's the first chunk
                                            if (description !== undefined || status === "in-progress") {
                                                return [
                                                    ...prevArtifacts,
                                                    {
                                                        filename,
                                                        description: description || null,
                                                        mime_type: mime_type || "application/octet-stream",
                                                        size: bytes_transferred || 0,
                                                        last_modified: new Date().toISOString(),
                                                        uri: `artifact://${sessionId}/${filename}`,
                                                        accumulatedContent: status === "in-progress" && artifact_chunk ? artifact_chunk : undefined,
                                                        isAccumulatedContentPlainText: status === "in-progress" && artifact_chunk ? true : false,
                                                        needsEmbedResolution: status === "completed" ? true : false,
                                                    },
                                                ];
                                            }
                                        }
                                        return prevArtifacts;
                                    });

                                    // Trigger auto-download AFTER state update (outside the setter)
                                    if (shouldAutoDownload) {
                                        setTimeout(() => {
                                            downloadAndResolveArtifact(filename).catch(err => {
                                                console.error(`Auto-download failed for ${filename}:`, err);
                                            });
                                        }, 100);
                                    }

                                    setMessages(prev => {
                                        const newMessages = [...prev];
                                        let agentMessageIndex = newMessages.findLastIndex(m => !m.isUser && m.taskId === currentTaskIdFromResult);

                                        if (agentMessageIndex === -1) {
                                            const newAgentMessage: MessageFE = {
                                                role: "agent",
                                                parts: [],
                                                taskId: currentTaskIdFromResult,
                                                isUser: false,
                                                isComplete: false,
                                                isStatusBubble: false,
                                                metadata: { lastProcessedEventSequence: currentEventSequence },
                                            };
                                            newMessages.push(newAgentMessage);
                                            agentMessageIndex = newMessages.length - 1;
                                        }

                                        const agentMessage = { ...newMessages[agentMessageIndex], parts: [...newMessages[agentMessageIndex].parts] };
                                        agentMessage.isStatusBubble = false;
                                        const artifactPartIndex = agentMessage.parts.findIndex(p => p.kind === "artifact" && p.name === filename);

                                        if (status === "in-progress") {
                                            if (artifactPartIndex > -1) {
                                                const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
                                                // Create a new part object with immutable update
                                                const updatedPart: ArtifactPart = {
                                                    ...existingPart,
                                                    bytesTransferred: bytes_transferred,
                                                    status: "in-progress",
                                                };
                                                agentMessage.parts[artifactPartIndex] = updatedPart;
                                            } else {
                                                const newPart: ArtifactPart = {
                                                    kind: "artifact",
                                                    status: "in-progress",
                                                    name: filename,
                                                    bytesTransferred: bytes_transferred,
                                                };
                                                agentMessage.parts.push(newPart);
                                            }
                                        } else if (status === "completed") {
                                            const fileAttachment: FileAttachment = {
                                                name: filename,
                                                mime_type,
                                                uri: version !== undefined ? `artifact://${sessionId}/${filename}?version=${version}` : `artifact://${sessionId}/${filename}`,
                                            };
                                            if (artifactPartIndex > -1) {
                                                const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
                                                // Create a new part object with immutable update
                                                const updatedPart: ArtifactPart = {
                                                    ...existingPart,
                                                    status: "completed",
                                                    file: fileAttachment,
                                                };
                                                // Remove bytesTransferred for completed artifacts
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
                                            void artifactsRefetch();
                                        } else {
                                            // status === "failed"
                                            const errorMsg = `Failed to create artifact: ${filename}`;
                                            if (artifactPartIndex > -1) {
                                                const existingPart = agentMessage.parts[artifactPartIndex] as ArtifactPart;
                                                // Create a new part object with immutable update
                                                const updatedPart: ArtifactPart = {
                                                    ...existingPart,
                                                    status: "failed",
                                                    error: errorMsg,
                                                };
                                                // Remove bytesTransferred for failed artifacts
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

                                        newMessages[agentMessageIndex] = agentMessage;

                                        // Filter out OTHER generic status bubbles, but keep our message.
                                        const finalMessages = newMessages.filter(m => !m.isStatusBubble || m.parts.some(p => p.kind === "artifact" || p.kind === "file"));
                                        return finalMessages;
                                    });
                                    // Return immediately to prevent the generic status handler from running
                                    return;
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
                                        setMessages(prev => [...prev, authMessage]);
                                    }
                                    break;
                                }
                                default:
                                    console.warn("Received unknown data part type:", data.type);
                            }
                        }
                    }
                }
            }

            const newContentParts = messageToProcess?.parts?.filter(p => p.kind !== "data") || [];
            const hasNewFiles = newContentParts.some(p => p.kind === "file");

            // Update UI state based on processed parts
            setMessages(prevMessages => {
                const newMessages = [...prevMessages];

                let lastMessage = newMessages[newMessages.length - 1];

                // Remove old generic status bubble
                if (lastMessage?.isStatusBubble) {
                    newMessages.pop();
                    lastMessage = newMessages[newMessages.length - 1];
                }

                // Check if we can append to the last message
                if (lastMessage && !lastMessage.isUser && lastMessage.taskId === (result as TaskStatusUpdateEvent).taskId && newContentParts.length > 0) {
                    const updatedMessage: MessageFE = {
                        ...lastMessage,
                        parts: [...lastMessage.parts, ...newContentParts],
                        isComplete: isFinalEvent || hasNewFiles,
                        metadata: {
                            ...lastMessage.metadata,
                            lastProcessedEventSequence: currentEventSequence,
                        },
                    };
                    newMessages[newMessages.length - 1] = updatedMessage;
                } else {
                    // Only create a new bubble if there is visible content to render.
                    const hasVisibleContent = newContentParts.some(p => (p.kind === "text" && (p as TextPart).text.trim()) || p.kind === "file");
                    if (hasVisibleContent) {
                        const newBubble: MessageFE = {
                            role: "agent",
                            parts: newContentParts,
                            taskId: (result as TaskStatusUpdateEvent).taskId,
                            isUser: false,
                            isComplete: isFinalEvent || hasNewFiles,
                            metadata: {
                                messageId: rpcResponse.id?.toString() || `msg-${v4()}`,
                                sessionId: (result as TaskStatusUpdateEvent).contextId,
                                lastProcessedEventSequence: currentEventSequence,
                            },
                        };
                        newMessages.push(newBubble);
                    }
                }

                // Add a new status bubble if the task is not over
                if (isFinalEvent) {
                    latestStatusText.current = null;
                    // Finalize any lingering in-progress artifact parts for this task
                    // With the new artifact_completed signal, in-progress artifacts should only remain if they truly failed
                    for (let i = newMessages.length - 1; i >= 0; i--) {
                        const msg = newMessages[i];
                        if (msg.taskId === currentTaskIdFromResult && msg.parts.some(p => p.kind === "artifact" && p.status === "in-progress")) {
                            const finalParts: PartFE[] = msg.parts.map(p => {
                                if (p.kind === "artifact" && p.status === "in-progress") {
                                    // Mark in-progress artifact as failed since artifact_completed signal should have arrived
                                    return { ...p, status: "failed", error: `Artifact creation for "${p.name}" did not complete.` };
                                }
                                return p;
                            });

                            newMessages[i] = {
                                ...msg,
                                parts: finalParts,
                                isError: true, // Mark as error because artifacts failed
                                isComplete: true,
                            };
                        }
                    }
                    // Explicitly mark the last message as complete on the final event
                    const taskMessageIndex = newMessages.findLastIndex(msg => !msg.isUser && msg.taskId === currentTaskIdFromResult);

                    if (taskMessageIndex !== -1) {
                        newMessages[taskMessageIndex] = {
                            ...newMessages[taskMessageIndex],
                            isComplete: true,
                            metadata: { ...newMessages[taskMessageIndex].metadata, lastProcessedEventSequence: currentEventSequence },
                        };
                    }
                }

                return newMessages;
            });

            // Finalization logic
            if (isFinalEvent) {
                if (isCancellingRef.current) {
                    addNotification("Task cancelled.", "success");
                    if (cancelTimeoutRef.current) clearTimeout(cancelTimeoutRef.current);
                    setIsCancelling(false);
                }

                // Save complete task when agent response is done (Step 10.5-10.9)
                // Note: For background tasks, the backend TaskLoggerService handles saving automatically
                // For non-background tasks, we save here
                if (currentTaskIdFromResult) {
                    const isBackgroundTask = isTaskRunningInBackground(currentTaskIdFromResult);

                    // Only save non-background tasks from frontend
                    // Background tasks are saved by TaskLoggerService to avoid race conditions
                    if (!isBackgroundTask) {
                        // Use messagesRef to get the latest messages
                        const taskMessages = messagesRef.current.filter(msg => msg.taskId === currentTaskIdFromResult && !msg.isStatusBubble);

                        if (taskMessages.length > 0) {
                            // Serialize all message bubbles
                            const messageBubbles = taskMessages.map(serializeMessageBubble);

                            // Extract user message text
                            const userMessage = taskMessages.find(m => m.isUser);
                            const userMessageText =
                                userMessage?.parts
                                    ?.filter(p => p.kind === "text")
                                    .map(p => (p as TextPart).text)
                                    .join("") || "";

                            // Determine task status
                            const hasError = taskMessages.some(m => m.isError);
                            const taskStatus = hasError ? "error" : "completed";

                            // Get the session ID from the task's context
                            const taskSessionId = (result as TaskStatusUpdateEvent).contextId || sessionId;

                            // Save complete task
                            saveTaskToBackend(
                                {
                                    task_id: currentTaskIdFromResult,
                                    user_message: userMessageText,
                                    message_bubbles: messageBubbles,
                                    task_metadata: {
                                        schema_version: CURRENT_SCHEMA_VERSION,
                                        status: taskStatus,
                                        agent_name: selectedAgentName,
                                    },
                                },
                                taskSessionId
                            )
                                .then(saved => {
                                    if (saved && typeof window !== "undefined") {
                                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                                    }
                                })
                                .catch(error => {
                                    console.error(`[ChatProvider] Error saving task ${currentTaskIdFromResult}:`, error);
                                });
                        }
                    } else {
                        // For background tasks, just unregister after completion
                        unregisterBackgroundTask(currentTaskIdFromResult);

                        // Trigger session list refresh
                        if (typeof window !== "undefined") {
                            window.dispatchEvent(new CustomEvent("new-chat-session"));
                        }
                    }
                }

                // Mark all in-progress artifacts as completed when task finishes
                setMessages(currentMessages => {
                    return currentMessages.map(msg => {
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
                                    const completedPart: ArtifactPart = {
                                        kind: "artifact",
                                        status: "completed",
                                        name: artifactPart.name,
                                        file: fileAttachment,
                                    };
                                    return completedPart;
                                }
                                return part;
                            }),
                        };
                    });
                });

                // Background task unregistration is now handled in the saveTaskToBackend promise above
                // This ensures the database save completes before we unregister and refresh

                setIsResponding(false);
                closeCurrentEventSource();
                setCurrentTaskId(null);
                isFinalizing.current = true;
                void artifactsRefetch();
                setTimeout(() => {
                    isFinalizing.current = false;
                }, 100);
            }
        },
        [
            addNotification,
            closeCurrentEventSource,
            artifactsRefetch,
            sessionId,
            selectedAgentName,
            saveTaskToBackend,
            serializeMessageBubble,
            downloadAndResolveArtifact,
            setArtifacts,
            isTaskRunningInBackground,
            updateTaskTimestamp,
            unregisterBackgroundTask,
        ]
    );

    const handleNewSession = useCallback(
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
            // Artifacts will be automatically refreshed by useArtifacts hook when sessionId changes

            // Dispatch event to focus chat input
            if (typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("focus-chat-input"));
            }

            // Note: No session events dispatched here since no session exists yet.
            // Session creation event will be dispatched when first message creates the actual session.
        },
        [isResponding, currentTaskId, selectedAgentName, isCancelling, closeCurrentEventSource, activeProject, setActiveProject, closePreview, isTaskRunningInBackground]
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

    const handleSwitchSession = useCallback(
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
                isFinalizing.current = false;
                latestStatusText.current = null;
                sseEventSequenceRef.current = 0;

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
                            // Task is no longer running - unregister it immediately
                            // This prevents the SSE useEffect from trying to reconnect
                            console.log(`[ChatProvider] Background task ${bgTask.taskId} is not running, unregistering`);
                            unregisterBackgroundTask(bgTask.taskId);
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
            closeCurrentEventSource,
            isResponding,
            currentTaskId,
            selectedAgentName,
            isCancelling,
            loadSessionTasks,
            activeProject,
            projects,
            setActiveProject,
            closePreview,
            setError,
            backgroundTasks,
            checkTaskStatus,
            sessionId,
            unregisterBackgroundTask,
            isTaskRunningInBackground,
        ]
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
    }, [isResponding, isCancelling, currentTaskId, addNotification, setError, closeCurrentEventSource]);

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
    }, [closeCurrentEventSource, isResponding, setError]);

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
        async (event: FormEvent, files?: File[] | null, userInputText?: string | null, overrideSessionId?: string | null) => {
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
                    messageMetadata.background_execution = true;
                    messageMetadata.max_execution_time_ms = backgroundTasksDefaultTimeoutMs ?? 3600000; // Default 1 hour
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
                        const textParts = userMsg.parts.filter(p => p.kind === "text") as TextPart[];
                        const combinedText = textParts
                            .map(p => p.text)
                            .join(" ")
                            .trim();

                        if (combinedText) {
                            newSessionName = combinedText.length > 100 ? `${combinedText.substring(0, 100)}...` : combinedText;
                        } else if (currentFiles.length > 0) {
                            // No text, but files were sent - derive name from files
                            if (currentFiles.length === 1) {
                                newSessionName = currentFiles[0].name;
                            } else {
                                newSessionName = `${currentFiles[0].name} +${currentFiles.length - 1} more`;
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
                            message_bubbles: [serializeMessageBubble(userMsg)],
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
            sessionId,
            isResponding,
            isCancelling,
            selectedAgentName,
            closeCurrentEventSource,
            uploadArtifactFile,
            updateSessionName,
            saveTaskToBackend,
            serializeMessageBubble,
            activeProject,
            cleanupUploadedFiles,
            setError,
            backgroundTasksDefaultTimeoutMs,
            backgroundTasksEnabled,
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
        const handleSessionMoved = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { sessionId: movedSessionId, projectId: newProjectId } = customEvent.detail;

            // If the moved session is the current session, update the project context
            if (movedSessionId === sessionId) {
                // Set flag to prevent handleNewSession from being triggered by this project change
                isSessionMoveRef.current = true;

                if (newProjectId) {
                    // Session moved to a project - activate that project
                    const project = projects.find((p: Project) => p.id === newProjectId);
                    if (project) {
                        setActiveProject(project);
                    }
                } else {
                    // Session moved out of project - deactivate project context
                    setActiveProject(null);
                }
            }
        };

        window.addEventListener("session-moved", handleSessionMoved);
        return () => {
            window.removeEventListener("session-moved", handleSessionMoved);
        };
    }, [sessionId, projects, setActiveProject]);

    useEffect(() => {
        // Listen for background task completion events
        // When a background task completes, reload ANY session it belongs to (not just current)
        // This ensures we get the latest data even if the task completed while we were in a different session
        const handleBackgroundTaskCompleted = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { taskId: completedTaskId } = customEvent.detail;

            // Find the completed task
            const completedTask = backgroundTasksRef.current.find(t => t.taskId === completedTaskId);
            if (completedTask) {
                console.log(`[ChatProvider] Background task ${completedTaskId} completed, will reload session ${completedTask.sessionId} after delay`);
                // Wait a bit to ensure any pending operations complete
                setTimeout(async () => {
                    // Reload the session if it's currently active
                    if (currentSessionIdRef.current === completedTask.sessionId) {
                        console.log(`[ChatProvider] Reloading current session ${completedTask.sessionId} to get latest data`);
                        await loadSessionTasks(completedTask.sessionId);
                    }
                }, 1500); // Increased delay to ensure save completes
            }
        };

        window.addEventListener("background-task-completed", handleBackgroundTaskCompleted);
        return () => {
            window.removeEventListener("background-task-completed", handleBackgroundTaskCompleted);
        };
    }, [loadSessionTasks]);

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
    }, [agents, configWelcomeMessage, messages.length, selectedAgentName, sessionId, isLoadingSession, activeProject]);

    // Store the latest handlers in refs so they can be accessed without triggering effect re-runs
    const handleSseMessageRef = useRef(handleSseMessage);
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
            const accessToken = getAccessToken();

            const bgTask = backgroundTasksRef.current.find(t => t.taskId === currentTaskId);
            const isReconnecting = bgTask !== undefined;

            const params = new URLSearchParams();
            if (accessToken) {
                params.append("token", accessToken);
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
                handleSseMessageRef.current(event);
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
    }, [currentTaskId, closeCurrentEventSource]);

    const contextValue: ChatContextValue = {
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
        artifactsLoading,
        artifactsRefetch,
        setArtifacts,
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
    };

    return (
        <ChatContext.Provider value={contextValue}>
            {children}
            <ErrorDialog />
        </ChatContext.Provider>
    );
};
