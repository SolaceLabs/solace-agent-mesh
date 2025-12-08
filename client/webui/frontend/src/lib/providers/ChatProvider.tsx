/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useCallback, useEffect, useRef, useMemo, type FormEvent, type ReactNode } from "react";
import { v4 } from "uuid";

import { useConfigContext, useArtifacts, useAgentCards, useErrorDialog, useBackgroundTaskMonitor } from "@/lib/hooks";
import { useProjectContext, registerProjectDeletedCallback } from "@/lib/providers";

import { authenticatedFetch, fetchJsonWithError, fetchWithError, getAccessToken, getErrorMessage, submitFeedback } from "@/lib/utils/api";
import { createFileSizeErrorMessage } from "@/lib/utils/file-validation";
import { ChatContext, type ChatContextValue, type PendingPromptData } from "@/lib/contexts";
import type {
    ArtifactInfo,
    ArtifactRenderingState,
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
} from "@/lib/types";

// Type for tasks loaded from the API
interface TaskFromAPI {
    taskId: string;
    messageBubbles: string; // JSON string
    taskMetadata: string | null; // JSON string
    createdTime: number;
    userMessage?: string;
}

// Schema version for data migration purposes
const CURRENT_SCHEMA_VERSION = 1;

// Migration function: V0 -> V1 (adds schema_version to tasks without one)
const migrateV0ToV1 = (task: any): any => {
    return {
        ...task,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 1,
        },
    };
};

// Migration registry: maps version numbers to migration functions

const MIGRATIONS: Record<number, (task: any) => any> = {
    0: migrateV0ToV1,
    // Uncomment when future branch merges:
    // 1: migrateV1ToV2,
};

const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB

const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = error => reject(error);
    });

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, configServerUrl, persistenceEnabled, configCollectFeedback, backgroundTasksEnabled, backgroundTasksDefaultTimeoutMs } = useConfigContext();
    const apiPrefix = useMemo(() => `${configServerUrl}/api/v1`, [configServerUrl]);
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

    // Track in-flight artifact preview fetches to prevent duplicates
    const artifactFetchInProgressRef = useRef<Set<string>>(new Set());
    const artifactDownloadInProgressRef = useRef<Set<string>>(new Set());

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

    // Delete Modal State
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [artifactToDelete, setArtifactToDelete] = useState<ArtifactInfo | null>(null);

    // Chat Side Panel Edit Mode State
    const [isArtifactEditMode, setIsArtifactEditMode] = useState<boolean>(false);
    const [selectedArtifactFilenames, setSelectedArtifactFilenames] = useState<Set<string>>(new Set());
    const [isBatchDeleteModalOpen, setIsBatchDeleteModalOpen] = useState<boolean>(false);

    // Preview State
    const [previewArtifactFilename, setPreviewArtifactFilename] = useState<string | null>(null);
    const [previewedArtifactAvailableVersions, setPreviewedArtifactAvailableVersions] = useState<number[] | null>(null);
    const [currentPreviewedVersionNumber, setCurrentPreviewedVersionNumber] = useState<number | null>(null);
    const [previewFileContent, setPreviewFileContent] = useState<FileAttachment | null>(null);

    // Derive previewArtifact from artifacts array to ensure it's always up-to-date
    const previewArtifact = useMemo(() => {
        if (!previewArtifactFilename) return null;
        return artifacts.find(a => a.filename === previewArtifactFilename) || null;
    }, [artifacts, previewArtifactFilename]);

    // Artifact Rendering State
    const [artifactRenderingState, setArtifactRenderingState] = useState<ArtifactRenderingState>({
        expandedArtifacts: new Set<string>(),
    });

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

    // Background Task Monitoring (placed after addNotification is defined)
    const {
        backgroundTasks,
        notifications: backgroundNotifications,
        registerBackgroundTask,
        unregisterBackgroundTask,
        updateTaskTimestamp,
        isTaskRunningInBackground,
        checkTaskStatus,
    } = useBackgroundTaskMonitor({
        apiPrefix,
        userId: "sam_dev_user", // TODO: Get from auth context when available
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
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${effectiveSessionId}/chat-tasks`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        taskId: taskData.task_id,
                        userMessage: taskData.user_message,
                        // Serialize to JSON strings before sending
                        messageBubbles: JSON.stringify(taskData.message_bubbles),
                        taskMetadata: taskData.task_metadata ? JSON.stringify(taskData.task_metadata) : null,
                    }),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Failed saving task" }));
                    throw new Error(errorData.message || `HTTP error ${response.status}`);
                }
                return true;
            } catch (error) {
                console.error(`Failed saving task ${taskData.task_id}:`, error);
                // Don't throw - saving is best-effort and silent per NFR-1
                return false;
            } finally {
                // Always remove from saving set after a delay to handle rapid re-renders
                setTimeout(() => {
                    savingTasksRef.current.delete(taskData.task_id);
                }, 100);
            }
        },
        [apiPrefix, sessionId, persistenceEnabled]
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
    const deserializeTaskToMessages = useCallback((task: { taskId: string; messageBubbles: any[]; taskMetadata?: any; createdTime: number }, sessionId: string): MessageFE[] => {
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
    }, []);

    // Helper function to apply migrations to a task
    const migrateTask = useCallback((task: any): any => {
        const version = task.taskMetadata?.schema_version || 0;

        if (version >= CURRENT_SCHEMA_VERSION) {
            // Already at current version
            return task;
        }

        // Apply migrations sequentially
        let migratedTask = task;
        for (let v = version; v < CURRENT_SCHEMA_VERSION; v++) {
            const migrationFunc = MIGRATIONS[v];
            if (migrationFunc) {
                migratedTask = migrationFunc(migratedTask);
                console.log(`Migrated task ${task.taskId} from v${v} to v${v + 1}`);
            } else {
                console.warn(`No migration function found for version ${v}`);
            }
        }

        return migratedTask;
    }, []);

    // Helper function to load session tasks and reconstruct messages
    const loadSessionTasks = useCallback(
        async (sessionId: string) => {
            const data = await fetchJsonWithError(`${apiPrefix}/sessions/${sessionId}/chat-tasks`);

            // Check if this session is still active before processing
            if (currentSessionIdRef.current !== sessionId) {
                console.log(`Session ${sessionId} is no longer the active session: ${currentSessionIdRef.current}`);
                return;
            }

            // Parse JSON strings from backend
            const tasks = data.tasks || [];
            const parsedTasks = tasks.map((task: TaskFromAPI) => ({
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
        [apiPrefix, deserializeTaskToMessages, migrateTask]
    );

    const uploadArtifactFile = useCallback(
        async (file: File, overrideSessionId?: string, description?: string, silent: boolean = false): Promise<{ uri: string; sessionId: string } | { error: string } | null> => {
            const effectiveSessionId = overrideSessionId || sessionId;
            const formData = new FormData();
            formData.append("upload_file", file);
            formData.append("filename", file.name);
            // Send sessionId as form field (can be empty string for new sessions)
            formData.append("sessionId", effectiveSessionId || "");

            // Add description as metadata if provided
            if (description) {
                const metadata = { description };
                formData.append("metadata_json", JSON.stringify(metadata));
            }

            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/upload`, {
                    method: "POST",
                    body: formData,
                });

                // Special handling for 413 status before checking response.ok
                if (response.status === 413) {
                    const errorData = await response.json().catch(() => ({ message: `Failed to upload ${file.name}.` }));
                    // Extract file size information if available and use common utility
                    const actualSize = errorData.actual_size_bytes;
                    const maxSize = errorData.max_size_bytes;

                    const errorMessage = actualSize && maxSize ? createFileSizeErrorMessage(file.name, actualSize, maxSize) : errorData.message || `File "${file.name}" exceeds the maximum allowed size.`;

                    setError({ title: "File Upload Failed", error: errorMessage });
                    return { error: errorMessage };
                }

                // For all other errors, use be error
                if (!response.ok) {
                    throw new Error(
                        await response
                            .json()
                            .then(d => d.message)
                            .catch(() => `Failed to upload ${file.name}.`)
                    );
                }

                const result = await response.json();
                if (!silent) {
                    addNotification(`File "${file.name}" uploaded.`, "success");
                }
                await artifactsRefetch();
                // Return both URI and sessionId (backend may have created a new session)
                return result.uri && result.sessionId ? { uri: result.uri, sessionId: result.sessionId } : null;
            } catch (error) {
                const errorMessage = getErrorMessage(error, `Failed to upload "${file.name}".`);
                setError({ title: "File Upload Failed", error: errorMessage });
                return { error: errorMessage };
            }
        },
        [apiPrefix, sessionId, addNotification, artifactsRefetch, setError]
    );

    // Session State
    const [sessionName, setSessionName] = useState<string | null>(null);
    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);
    const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);

    const deleteArtifactInternal = useCallback(
        async (filename: string) => {
            try {
                await fetchWithError(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                });
                addNotification(`File "${filename}" deleted.`, "success");
                artifactsRefetch();
            } catch (error) {
                setError({ title: "File Deletion Failed", error: getErrorMessage(error, `Failed to delete ${filename}.`) });
            }
        },
        [apiPrefix, sessionId, addNotification, artifactsRefetch, setError]
    );

    const openDeleteModal = useCallback((artifact: ArtifactInfo) => {
        setArtifactToDelete(artifact);
        setIsDeleteModalOpen(true);
    }, []);

    const closeDeleteModal = useCallback(() => {
        setArtifactToDelete(null);
        setIsDeleteModalOpen(false);
    }, []);

    // Wrapper function to set preview artifact by filename
    // IMPORTANT: Must be defined before confirmDelete to avoid circular dependency
    const setPreviewArtifact = useCallback((artifact: ArtifactInfo | null) => {
        setPreviewArtifactFilename(artifact?.filename || null);
    }, []);

    const confirmDelete = useCallback(async () => {
        if (artifactToDelete) {
            // Check if the artifact being deleted is currently being previewed
            const isCurrentlyPreviewed = previewArtifact?.filename === artifactToDelete.filename;

            await deleteArtifactInternal(artifactToDelete.filename);

            // If the deleted artifact was being previewed, go back to file list
            if (isCurrentlyPreviewed) {
                setPreviewArtifact(null);
            }
        }
        closeDeleteModal();
    }, [artifactToDelete, deleteArtifactInternal, closeDeleteModal, previewArtifact, setPreviewArtifact]);

    const handleDeleteSelectedArtifacts = useCallback(() => {
        if (selectedArtifactFilenames.size === 0) {
            return;
        }
        setIsBatchDeleteModalOpen(true);
    }, [selectedArtifactFilenames]);

    const confirmBatchDeleteArtifacts = useCallback(async () => {
        setIsBatchDeleteModalOpen(false);
        const filenamesToDelete = Array.from(selectedArtifactFilenames);
        let successCount = 0;
        let errorCount = 0;
        for (const filename of filenamesToDelete) {
            try {
                await fetchWithError(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                });
                successCount++;
            } catch (error: unknown) {
                console.error(error);
                errorCount++;
            }
        }
        if (successCount > 0) addNotification(`${successCount} files(s) deleted.`, "success");
        if (errorCount > 0) {
            setError({ title: "File Deletion Failed", error: `${errorCount} file(s) failed to delete.` });
        }
        artifactsRefetch();
        setSelectedArtifactFilenames(new Set());
        setIsArtifactEditMode(false);
    }, [selectedArtifactFilenames, addNotification, artifactsRefetch, apiPrefix, sessionId, setError]);

    const openArtifactForPreview = useCallback(
        async (artifactFilename: string): Promise<FileAttachment | null> => {
            // Prevent duplicate fetches for the same file
            if (artifactFetchInProgressRef.current.has(artifactFilename)) {
                return null;
            }

            // Mark this file as being fetched
            artifactFetchInProgressRef.current.add(artifactFilename);

            // Only clear state if this is a different file from what we're currently previewing
            // This prevents clearing state during duplicate fetch attempts
            if (previewArtifactFilename !== artifactFilename) {
                setPreviewedArtifactAvailableVersions(null);
                setCurrentPreviewedVersionNumber(null);
                setPreviewFileContent(null);
            }
            try {
                // Determine the correct URL based on context
                let versionsUrl: string;
                if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                    versionsUrl = `${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions`;
                } else if (activeProject?.id) {
                    versionsUrl = `${apiPrefix}/artifacts/null/${encodeURIComponent(artifactFilename)}/versions?project_id=${activeProject.id}`;
                } else {
                    throw new Error("No valid context for artifact preview");
                }

                const availableVersions: number[] = await fetchJsonWithError(versionsUrl);
                if (!availableVersions || availableVersions.length === 0) throw new Error("No versions available");
                setPreviewedArtifactAvailableVersions(availableVersions.sort((a, b) => a - b));
                const latestVersion = Math.max(...availableVersions);
                setCurrentPreviewedVersionNumber(latestVersion);
                let contentUrl: string;
                if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                    contentUrl = `${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions/${latestVersion}`;
                } else if (activeProject?.id) {
                    contentUrl = `${apiPrefix}/artifacts/null/${encodeURIComponent(artifactFilename)}/versions/${latestVersion}?project_id=${activeProject.id}`;
                } else {
                    throw new Error("No valid context for artifact content");
                }

                const contentResponse = await fetchWithError(contentUrl);

                // Get MIME type from response headers - this is the correct MIME type for this specific version
                const contentType = contentResponse.headers.get("Content-Type") || "application/octet-stream";
                // Strip charset and other parameters from Content-Type
                const mimeType = contentType.split(";")[0].trim();

                const blob = await contentResponse.blob();
                const base64Content = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result?.toString().split(",")[1] || "");
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
                const artifactInfo = artifacts.find(art => art.filename === artifactFilename);
                const fileData: FileAttachment = {
                    name: artifactFilename,
                    // Use MIME type from response headers (version-specific), not from artifact list (latest version)
                    mime_type: mimeType,
                    content: base64Content,
                    last_modified: artifactInfo?.last_modified || new Date().toISOString(),
                };
                setPreviewFileContent(fileData);
                return fileData;
            } catch (error) {
                setError({ title: "Artifact Preview Failed", error: getErrorMessage(error, "Failed to load artifact preview.") });
                return null;
            } finally {
                // Remove from in-progress set immediately when done
                artifactFetchInProgressRef.current.delete(artifactFilename);
            }
        },
        [apiPrefix, sessionId, activeProject?.id, artifacts, previewArtifactFilename, setError]
    );

    const navigateArtifactVersion = useCallback(
        async (artifactFilename: string, targetVersion: number): Promise<FileAttachment | null> => {
            // If versions aren't loaded yet, this is likely a timing issue where this was called
            // before openArtifactForPreview completed. Just silently return - the artifact will
            // show the latest version when loaded, which is acceptable behavior.
            if (!previewedArtifactAvailableVersions || previewedArtifactAvailableVersions.length === 0) {
                return null;
            }

            // Now check if the specific version exists
            if (!previewedArtifactAvailableVersions.includes(targetVersion)) {
                console.warn(`Requested version ${targetVersion} not available for ${artifactFilename}`);
                return null;
            }
            setPreviewFileContent(null);
            try {
                // Determine the correct URL based on context
                let contentUrl: string;
                if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                    contentUrl = `${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions/${targetVersion}`;
                } else if (activeProject?.id) {
                    contentUrl = `${apiPrefix}/artifacts/null/${encodeURIComponent(artifactFilename)}/versions/${targetVersion}?project_id=${activeProject.id}`;
                } else {
                    throw new Error("No valid context for artifact navigation");
                }

                const contentResponse = await fetchWithError(contentUrl);

                // Get MIME type from response headers - this is the correct MIME type for this specific version
                const contentType = contentResponse.headers.get("Content-Type") || "application/octet-stream";
                // Strip charset and other parameters from Content-Type
                const mimeType = contentType.split(";")[0].trim();

                const blob = await contentResponse.blob();
                const base64Content = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result?.toString().split(",")[1] || "");
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
                const artifactInfo = artifacts.find(art => art.filename === artifactFilename);
                const fileData: FileAttachment = {
                    name: artifactFilename,
                    // Use MIME type from response headers (version-specific), not from artifact list (latest version)
                    mime_type: mimeType,
                    content: base64Content,
                    last_modified: artifactInfo?.last_modified || new Date().toISOString(),
                };
                setCurrentPreviewedVersionNumber(targetVersion);
                setPreviewFileContent(fileData);
                return fileData;
            } catch (error) {
                setError({ title: "Artifact Version Preview Failed", error: getErrorMessage(error, "Failed to fetch artifact version.") });
                return null;
            }
        },
        [apiPrefix, artifacts, previewedArtifactAvailableVersions, sessionId, activeProject?.id, setError]
    );

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

    // Download and resolve artifact with embeds
    const downloadAndResolveArtifact = useCallback(
        async (filename: string): Promise<FileAttachment | null> => {
            // Prevent duplicate downloads for the same file
            if (artifactDownloadInProgressRef.current.has(filename)) {
                console.log(`[ChatProvider] Skipping duplicate download for ${filename} - already in progress`);
                return null;
            }

            // Mark this file as being downloaded
            artifactDownloadInProgressRef.current.add(filename);

            try {
                // Find the artifact in state
                const artifact = artifacts.find(art => art.filename === filename);
                if (!artifact) {
                    console.error(`Artifact ${filename} not found in state`);
                    return null;
                }

                // Fetch the latest version with embeds resolved
                const availableVersions: number[] = await fetchJsonWithError(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions`);
                if (!availableVersions || availableVersions.length === 0) {
                    throw new Error("No versions available");
                }

                const latestVersion = Math.max(...availableVersions);
                const contentResponse = await fetchWithError(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions/${latestVersion}`);
                const blob = await contentResponse.blob();
                const base64Content = await new Promise<string>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result?.toString().split(",")[1] || "");
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });

                const fileData: FileAttachment = {
                    name: filename,
                    mime_type: artifact.mime_type || "application/octet-stream",
                    content: base64Content,
                    last_modified: artifact.last_modified || new Date().toISOString(),
                };

                // Clear the accumulated content and flags after successful download
                setArtifacts(prevArtifacts => {
                    return prevArtifacts.map(art =>
                        art.filename === filename
                            ? {
                                  ...art,
                                  accumulatedContent: undefined,
                                  needsEmbedResolution: false,
                              }
                            : art
                    );
                });

                return fileData;
            } catch (error) {
                setError({ title: "File Download Failed", error: getErrorMessage(error, `Failed to download ${filename}.`) });
                return null;
            } finally {
                // Remove from in-progress set immediately when done
                artifactDownloadInProgressRef.current.delete(filename);
            }
        },
        [apiPrefix, sessionId, artifacts, setArtifacts, setError]
    );

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
                        } else if (part.metadata?.tool_name === "_notify_artifact_save") {
                            // Handle artifact completion notification
                            const artifactData = data as { filename: string; version: number; status: string };

                            if (artifactData.status === "success") {
                                // Mark the artifact as completed in the message parts
                                setMessages(currentMessages => {
                                    return currentMessages.map(msg => {
                                        if (msg.isUser || !msg.parts.some(p => p.kind === "artifact" && p.name === artifactData.filename)) {
                                            return msg;
                                        }

                                        return {
                                            ...msg,
                                            parts: msg.parts.map(part => {
                                                if (part.kind === "artifact" && (part as ArtifactPart).name === artifactData.filename) {
                                                    const fileAttachment: FileAttachment = {
                                                        name: artifactData.filename,
                                                        uri: `artifact://${sessionId}/${artifactData.filename}`,
                                                    };
                                                    return {
                                                        kind: "artifact",
                                                        status: "completed",
                                                        name: artifactData.filename,
                                                        file: fileAttachment,
                                                    } as ArtifactPart;
                                                }
                                                return part;
                                            }),
                                        };
                                    });
                                });
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
                    for (let i = newMessages.length - 1; i >= 0; i--) {
                        const msg = newMessages[i];
                        if (msg.taskId === currentTaskIdFromResult && msg.parts.some(p => p.kind === "artifact" && p.status === "in-progress")) {
                            const finalParts: PartFE[] = msg.parts.map(p => {
                                if (p.kind === "artifact" && p.status === "in-progress") {
                                    // Mark in-progress part as failed
                                    return { ...p, status: "failed", error: `Artifact creation for "${p.name}" did not complete.` };
                                }
                                return p;
                            });
                            newMessages[i] = {
                                ...msg,
                                parts: finalParts,
                                isError: true, // Mark as error because it didn't complete
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

            // Only cancel task if it's not a background task
            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                const isBackground = isTaskRunningInBackground(currentTaskId);

                if (!isBackground) {
                    try {
                        const cancelRequest = {
                            jsonrpc: "2.0",
                            id: `req-${v4()}`,
                            method: "tasks/cancel",
                            params: {
                                id: currentTaskId,
                            },
                        };
                        authenticatedFetch(`${apiPrefix}/tasks/${currentTaskId}:cancel`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(cancelRequest),
                            credentials: "include",
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
            setPreviewArtifact(null);
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
        [apiPrefix, isResponding, currentTaskId, selectedAgentName, isCancelling, closeCurrentEventSource, activeProject, setActiveProject, setPreviewArtifact, isTaskRunningInBackground]
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

            // Only cancel task if it's not a background task
            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                const isBackground = isTaskRunningInBackground(currentTaskId);

                if (!isBackground) {
                    try {
                        const cancelRequest = {
                            jsonrpc: "2.0",
                            id: `req-${v4()}`,
                            method: "tasks/cancel",
                            params: {
                                id: currentTaskId,
                            },
                        };
                        await authenticatedFetch(`${apiPrefix}/tasks/${currentTaskId}:cancel`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify(cancelRequest),
                            credentials: "include",
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
                const sessionData = await fetchJsonWithError(`${apiPrefix}/sessions/${newSessionId}`);
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
                setPreviewArtifact(null);
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
            apiPrefix,
            loadSessionTasks,
            activeProject,
            projects,
            setActiveProject,
            setPreviewArtifact,
            setError,
            isTaskRunningInBackground,
            backgroundTasks,
            checkTaskStatus,
            unregisterBackgroundTask,
        ]
    );

    const updateSessionName = useCallback(
        async (sessionId: string, newName: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: newName }),
                });

                // Special handling for 422 validation errors
                if (response.status === 422) {
                    throw new Error("Invalid name");
                }

                // For all other errors
                if (!response.ok) {
                    throw new Error(
                        await response
                            .json()
                            .then(d => d.message)
                            .catch(() => "Failed to update session name")
                    );
                }

                setSessionName(newName);
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                setError({ title: "Session Name Update Failed", error: getErrorMessage(error, "Failed to update session name.") });
            }
        },
        [apiPrefix, setError]
    );

    const deleteSession = useCallback(
        async (sessionIdToDelete: string) => {
            try {
                await fetchWithError(`${apiPrefix}/sessions/${sessionIdToDelete}`, {
                    method: "DELETE",
                });
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
        [apiPrefix, addNotification, handleNewSession, sessionId, setError]
    );

    // Artifact Rendering Actions
    const toggleArtifactExpanded = useCallback((filename: string) => {
        setArtifactRenderingState(prevState => {
            const newExpandedArtifacts = new Set(prevState.expandedArtifacts);

            if (newExpandedArtifacts.has(filename)) {
                newExpandedArtifacts.delete(filename);
            } else {
                newExpandedArtifacts.add(filename);
            }

            return {
                ...prevState,
                expandedArtifacts: newExpandedArtifacts,
            };
        });
    }, []);

    const isArtifactExpanded = useCallback(
        (filename: string) => {
            return artifactRenderingState.expandedArtifacts.has(filename);
        },
        [artifactRenderingState.expandedArtifacts]
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
                params: {
                    id: currentTaskId,
                },
            };

            const response = await authenticatedFetch(`${apiPrefix}/tasks/${currentTaskId}:cancel`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(cancelRequest),
            });

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
    }, [isResponding, isCancelling, currentTaskId, apiPrefix, addNotification, setError, closeCurrentEventSource]);

    const handleFeedbackSubmit = useCallback(
        async (taskId: string, feedbackType: "up" | "down", feedbackText: string) => {
            if (!sessionId) {
                console.error("Cannot submit feedback without a session ID.");
                return;
            }
            try {
                await submitFeedback({
                    taskId: taskId,
                    sessionId: sessionId,
                    feedbackType: feedbackType,
                    feedbackText: feedbackText,
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

    const cleanupUploadedFiles = useCallback(
        async (uploadedFiles: Array<{ filename: string; sessionId: string }>) => {
            if (uploadedFiles.length === 0) {
                return;
            }

            for (const { filename, sessionId: fileSessionId } of uploadedFiles) {
                try {
                    const deleteUrl = `${apiPrefix}/artifacts/${fileSessionId}/${encodeURIComponent(filename)}`;

                    // Use the session ID that was used during upload
                    await fetchWithError(deleteUrl, {
                        method: "DELETE",
                    });
                } catch (error) {
                    console.error(`[cleanupUploadedFiles] Exception while cleaning up file ${filename}:`, error);
                    // Continue cleanup even if one fails (intentionally silent)
                }
            }
        },
        [apiPrefix]
    );

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
                const result = await fetchJsonWithError(`${apiPrefix}/message:stream`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(sendMessageRequest),
                });

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
            apiPrefix,
            uploadArtifactFile,
            updateSessionName,
            saveTaskToBackend,
            serializeMessageBubble,
            activeProject,
            cleanupUploadedFiles,
            setError,
            registerBackgroundTask,
            backgroundTasksEnabled,
            backgroundTasksDefaultTimeoutMs,
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
        if (currentTaskId && apiPrefix) {
            const accessToken = getAccessToken();

            // Check if this is a reconnection to a background task
            // Use a ref to get the latest background tasks without triggering re-renders
            const bgTask = backgroundTasksRef.current.find(t => t.taskId === currentTaskId);
            const isReconnecting = bgTask !== undefined;

            // Build SSE URL with reconnection parameters if needed
            let eventSourceUrl = `${apiPrefix}/sse/subscribe/${currentTaskId}`;
            const params = new URLSearchParams();

            if (accessToken) {
                params.append("token", accessToken);
            }

            if (isReconnecting) {
                // For background task reconnection, always request full replay
                // The backend will replay ALL events from the beginning for background tasks
                // This ensures we can reconstruct the full message content after browser refresh
                params.append("reconnect", "true");
                params.append("last_event_timestamp", "0"); // Request all events from beginning
                console.log(`[ChatProvider] Reconnecting to background task ${currentTaskId} - requesting full event replay`);

                // Clear agent messages for this task before replaying
                // This prevents duplicate content when events are replayed
                setMessages(prev => {
                    const filtered = prev.filter(msg => {
                        // Keep user messages and messages from other tasks
                        if (msg.isUser) return true;
                        if (msg.taskId !== currentTaskId) return true;
                        // Remove agent messages for this task - they will be rebuilt from replayed events
                        return false;
                    });
                    return filtered;
                });
            }

            if (params.toString()) {
                eventSourceUrl += `?${params.toString()}`;
            }

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
    }, [currentTaskId, apiPrefix, closeCurrentEventSource]);

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
        openArtifactForPreview,
        navigateArtifactVersion,
        previewArtifact,
        setPreviewArtifact, // Now uses the wrapper function that sets filename
        updateSessionName,
        deleteSession,

        /** Artifact Rendering Actions */
        toggleArtifactExpanded,
        isArtifactExpanded,
        setArtifactRenderingState,
        artifactRenderingState,

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
