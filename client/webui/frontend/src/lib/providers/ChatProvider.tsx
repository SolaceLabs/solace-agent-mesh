import React, { useState, useCallback, useEffect, useRef, type FormEvent, type ReactNode, useMemo } from "react";
import { v4 } from "uuid";

import { useConfigContext, useArtifacts, useAgentCards } from "@/lib/hooks";

// Schema version for data migration purposes
const CURRENT_SCHEMA_VERSION = 1;

// Migration function: V0 -> V1 (adds schema_version to tasks without one)
const migrateV0ToV1 = (task: TaskDataV0): TaskDataV1 => {
    return {
        ...task,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 1,
        },
    };
};

// Migration registry: maps version numbers to migration functions
const MIGRATIONS: Record<number, (task: TaskDataAnyVersion) => TaskDataAnyVersion> = {
    0: migrateV0ToV1,
    // Uncomment when future branch merges:
    // 1: migrateV1ToV2,
};

import { authenticatedFetch, getAccessToken, submitFeedback } from "@/lib/utils/api";
import { ChatContext, type ChatContextValue } from "@/lib/contexts";
import type {
    ArtifactInfo,
    CancelTaskRequest,
    FileAttachment,
    FilePart,
    JSONRPCErrorResponse,
    Message,
    MessageFE,
    Notification,
    Part,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    Session,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
    TextPart,
} from "@/lib/types";
import type { MessageBubble, TaskMetadata, StoredTaskData } from "@/lib/types/storage";

interface ChatProviderProps {
    children: ReactNode;
}

// Version-specific task data types
interface TaskDataV0 {
    taskId: string;
    messageBubbles: unknown[];
    taskMetadata?: {
        // V0 has no schema_version
        [key: string]: unknown;
    } | null;
    createdTime: number;
    userMessage?: string;
}

interface TaskDataV1 {
    taskId: string;
    messageBubbles: unknown[];
    taskMetadata: {
        schema_version: 1;
        [key: string]: unknown;
    };
    createdTime: number;
    userMessage?: string;
}

// Union type for any version (used during migration)
type TaskDataAnyVersion = TaskDataV0 | TaskDataV1;

// Alias for the CURRENT version - this is what the rest of the code uses
type TaskDataCurrent = TaskDataV1;

// Type for tasks loaded from the API (always current version after migration)
interface TaskFromAPI {
    taskId: string;
    messageBubbles: string; // JSON string
    taskMetadata: string | null; // JSON string
    createdTime: number;
    userMessage?: string;
}

// File utils
const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB
const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = error => reject(error);
    });
};

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, configServerUrl, persistenceEnabled, configCollectFeedback } = useConfigContext();
    const apiPrefix = useMemo(() => `${configServerUrl}/api/v1`, [configServerUrl]);

    // State Variables from useChat
    const [sessionId, setSessionId] = useState<string>("");
    const [messages, setMessages] = useState<MessageFE[]>([]);
    const [userInput, setUserInput] = useState<string>("");
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const currentEventSource = useRef<EventSource | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false);
    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);

    // Refs
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);
    const isCancellingRef = useRef(isCancelling);
    const savingTasksRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        isCancellingRef.current = isCancelling;
    }, [isCancelling]);

    // Agents State
    const { agents, error: agentsError, isLoading: agentsLoading, refetch: agentsRefetch } = useAgentCards();

    // Chat Side Panel State
    const { artifacts, isLoading: artifactsLoading, refetch: artifactsRefetch } = useArtifacts(sessionId);

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
    const [previewArtifact, setPreviewArtifact] = useState<ArtifactInfo | null>(null);
    const [previewedArtifactAvailableVersions, setPreviewedArtifactAvailableVersions] = useState<number[] | null>(null);
    const [currentPreviewedVersionNumber, setCurrentPreviewedVersionNumber] = useState<number | null>(null);
    const [previewFileContent, setPreviewFileContent] = useState<FileAttachment | null>(null);

    // Session State
    const [sessionName, setSessionName] = useState<string | null>(null);
    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);

    // Feedback State
    const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, { type: "up" | "down"; text: string }>>({});

    // Notification Helper
    const addNotification = useCallback((message: string, type?: "success" | "info" | "error") => {
        setNotifications(prev => {
            const existingNotification = prev.find(n => n.message === message);

            if (existingNotification) {
                return prev;
            }

            const id = Date.now().toString();
            const newNotification = { id, message, type: type || "info" };

            setTimeout(() => {
                setNotifications(current => current.filter(n => n.id !== id));
            }, 3000);

            return [...prev, newNotification];
        });
    }, []);

    // Helper function to serialize a MessageFE to MessageBubble format for backend
    const serializeMessageBubble = useCallback((message: MessageFE): MessageBubble => {
        const textParts = message.parts?.filter(p => p.kind === "text") as TextPart[] | undefined;
        const combinedText = textParts?.map(p => p.text).join("") || "";

        return {
            id: message.metadata?.messageId || `msg-${v4()}`,
            type: message.isUser ? "user" : message.artifactNotification ? "artifact_notification" : "agent",
            text: combinedText,
            parts: message.parts,
            files: message.files,
            uploadedFiles: message.uploadedFiles?.map(f => ({
                name: f.name,
                type: f.type,
            })),
            artifactNotification: message.artifactNotification,
            isError: message.isError,
        };
    }, []);

    // Helper function to save task data to backend
    const saveTaskToBackend = useCallback(
        async (taskData: { task_id: string; user_message?: string; message_bubbles: MessageBubble[]; task_metadata?: TaskMetadata }) => {
            if (!persistenceEnabled || !sessionId) return;

            // Prevent duplicate saves (handles React Strict Mode + race conditions)
            if (savingTasksRef.current.has(taskData.task_id)) {
                return;
            }

            // Mark as saving
            savingTasksRef.current.add(taskData.task_id);

            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}/chat-tasks`, {
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
                    const errorData = await response.json().catch(() => ({ detail: "Failed to save task" }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
            } catch (error) {
                console.error(`Error saving task ${taskData.task_id}:`, error);
                // Don't throw - saving is best-effort and silent per NFR-1
            } finally {
                // Always remove from saving set after a delay to handle rapid re-renders
                setTimeout(() => {
                    savingTasksRef.current.delete(taskData.task_id);
                }, 100);
            }
        },
        [apiPrefix, sessionId, persistenceEnabled]
    );

    // Helper function to deserialize task data to MessageFE objects
    const deserializeTaskToMessages = useCallback(
        (task: StoredTaskData): MessageFE[] => {
            return task.messageBubbles.map(bubble => ({
                taskId: task.taskId,
                role: bubble.type === "user" ? "user" : "agent",
                parts: bubble.parts || [{ kind: "text", text: bubble.text || "" }],
                isUser: bubble.type === "user",
                isComplete: true,
                files: bubble.files,
                // uploadedFiles in storage is Array<{name, type}>, but MessageFE expects File[]
                // We can't reconstruct File objects from stored metadata, so omit this field
                uploadedFiles: undefined,
                artifactNotification: bubble.artifactNotification,
                isError: bubble.isError,
                metadata: {
                    messageId: bubble.id,
                    sessionId: sessionId,
                    lastProcessedEventSequence: 0,
                },
            }));
        },
        [sessionId]
    );

    // Helper function to apply migrations to a task
    const migrateTask = useCallback((task: TaskDataAnyVersion): TaskDataCurrent => {
        const version: number = (task.taskMetadata?.schema_version as number) || 0;

        if (version >= CURRENT_SCHEMA_VERSION) {
            // Already at current version
            return task as TaskDataCurrent;
        }

        // Apply migrations sequentially
        let migratedTask: TaskDataAnyVersion = task;
        for (let v = version; v < CURRENT_SCHEMA_VERSION; v++) {
            const migrationFunc = MIGRATIONS[v];
            if (migrationFunc) {
                migratedTask = migrationFunc(migratedTask);
                console.log(`Migrated task ${task.taskId} from v${v} to v${v + 1}`);
            } else {
                console.warn(`No migration function found for version ${v}`);
            }
        }

        return migratedTask as TaskDataCurrent;
    }, []);

    // Helper function to load session tasks and reconstruct messages
    const loadSessionTasks = useCallback(
        async (sessionId: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}/chat-tasks`);

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Failed to load session tasks" }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }

                const data = await response.json();
                const tasks = data.tasks || [];

                // Parse JSON strings from backend
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
                    const taskMessages = deserializeTaskToMessages(task);
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
            } catch (error) {
                console.error("Error loading session tasks:", error);
                addNotification("Error loading session history. Please try again.", "error");
                throw error;
            }
        },
        [apiPrefix, deserializeTaskToMessages, addNotification, migrateTask]
    );

    const uploadArtifactFile = useCallback(
        async (file: File, overrideSessionId?: string): Promise<{ uri: string; sessionId: string } | null> => {
            const currentSessionId = overrideSessionId || sessionId;
            const formData = new FormData();
            formData.append("upload_file", file);
            formData.append("filename", file.name);
            if (currentSessionId) {
                formData.append("sessionId", currentSessionId);
            }
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/upload`, {
                    method: "POST",
                    body: formData,
                    credentials: "include",
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: `Failed to upload ${file.name}` }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                const result = await response.json();
                const artifactData = result.data || result;
                addNotification(`Artifact "${file.name}" uploaded successfully.`);
                await artifactsRefetch();
                return { uri: artifactData.uri, sessionId: artifactData.sessionId };
            } catch (error) {
                addNotification(`Error uploading artifact "${file.name}": ${error instanceof Error ? error.message : "Unknown error"}`);
                return null;
            }
        },
        [apiPrefix, sessionId, addNotification, artifactsRefetch]
    );

    const deleteArtifactInternal = useCallback(
        async (filename: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                    credentials: "include",
                });
                if (!response.ok && response.status !== 204) {
                    const errorData = await response.json().catch(() => ({ detail: `Failed to delete ${filename}` }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification(`File "${filename}" deleted successfully.`);
                artifactsRefetch();
            } catch (error) {
                addNotification(`Error deleting file "${filename}": ${error instanceof Error ? error.message : "Unknown error"}`);
            }
        },
        [apiPrefix, sessionId, addNotification, artifactsRefetch]
    );

    const openDeleteModal = useCallback((artifact: ArtifactInfo) => {
        setArtifactToDelete(artifact);
        setIsDeleteModalOpen(true);
    }, []);

    const closeDeleteModal = useCallback(() => {
        setArtifactToDelete(null);
        setIsDeleteModalOpen(false);
    }, []);

    const confirmDelete = useCallback(async () => {
        if (artifactToDelete) {
            await deleteArtifactInternal(artifactToDelete.filename);
        }
        closeDeleteModal();
    }, [artifactToDelete, deleteArtifactInternal, closeDeleteModal]);

    const handleDeleteSelectedArtifacts = useCallback(() => {
        if (selectedArtifactFilenames.size === 0) {
            addNotification("No files selected for deletion.");
            return;
        }
        setIsBatchDeleteModalOpen(true);
    }, [selectedArtifactFilenames, addNotification]);

    const confirmBatchDeleteArtifacts = useCallback(async () => {
        setIsBatchDeleteModalOpen(false);
        const filenamesToDelete = Array.from(selectedArtifactFilenames);
        let successCount = 0;
        let errorCount = 0;
        for (const filename of filenamesToDelete) {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                    credentials: "include",
                });
                if (!response.ok && response.status !== 204) throw new Error(`Failed to delete ${filename}`);
                successCount++;
            } catch (error: unknown) {
                console.error(error);
                errorCount++;
            }
        }
        if (successCount > 0) addNotification(`${successCount} files(s) deleted successfully.`);
        if (errorCount > 0) addNotification(`Failed to delete ${errorCount} files(s).`);
        artifactsRefetch();
        setSelectedArtifactFilenames(new Set());
        setIsArtifactEditMode(false);
    }, [selectedArtifactFilenames, addNotification, artifactsRefetch, apiPrefix, sessionId]);

    const openArtifactForPreview = useCallback(
        async (artifactFilename: string): Promise<FileAttachment | null> => {
            setPreviewedArtifactAvailableVersions(null);
            setCurrentPreviewedVersionNumber(null);
            setPreviewFileContent(null);
            try {
                const versionsResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions`, { credentials: "include" });
                if (!versionsResponse.ok) throw new Error("Error fetching version list");
                const availableVersions: number[] = await versionsResponse.json();
                if (!availableVersions || availableVersions.length === 0) throw new Error("No versions available");
                setPreviewedArtifactAvailableVersions(availableVersions.sort((a, b) => a - b));
                const latestVersion = Math.max(...availableVersions);
                setCurrentPreviewedVersionNumber(latestVersion);
                const contentResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions/${latestVersion}`, { credentials: "include" });
                if (!contentResponse.ok) throw new Error("Error fetching latest version content");
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
                    mime_type: artifactInfo?.mime_type || "application/octet-stream",
                    content: base64Content,
                    last_modified: artifactInfo?.last_modified || new Date().toISOString(),
                };
                setPreviewFileContent(fileData);
                return fileData;
            } catch (error) {
                addNotification(`Error loading preview for ${artifactFilename}: ${error instanceof Error ? error.message : "Unknown error"}`);
                return null;
            }
        },
        [apiPrefix, sessionId, artifacts, addNotification]
    );

    const navigateArtifactVersion = useCallback(
        async (artifactFilename: string, targetVersion: number): Promise<FileAttachment | null> => {
            if (!previewedArtifactAvailableVersions || !previewedArtifactAvailableVersions.includes(targetVersion)) {
                addNotification(`Version ${targetVersion} is not available for ${artifactFilename}.`);
                return null;
            }
            setPreviewFileContent(null);
            try {
                const contentResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(artifactFilename)}/versions/${targetVersion}`, { credentials: "include" });
                if (!contentResponse.ok) throw new Error(`Error fetching version ${targetVersion}`);
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
                    mime_type: artifactInfo?.mime_type || "application/octet-stream",
                    content: base64Content,
                    last_modified: artifactInfo?.last_modified || new Date().toISOString(),
                };
                setCurrentPreviewedVersionNumber(targetVersion);
                setPreviewFileContent(fileData);
                return fileData;
            } catch (error) {
                addNotification(`Error loading version ${targetVersion}: ${error instanceof Error ? error.message : "Unknown error"}`);
                return null;
            }
        },
        [apiPrefix, addNotification, artifacts, previewedArtifactAvailableVersions, sessionId]
    );

    const openMessageAttachmentForPreview = useCallback(
        (file: FileAttachment) => {
            addNotification(`Loading preview for attached file: ${file.name}`);
            setPreviewFileContent(file);
            setPreviewedArtifactAvailableVersions(null);
            setCurrentPreviewedVersionNumber(null);
        },
        [addNotification]
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

    const handleSseMessage = useCallback(
        (event: MessageEvent) => {
            sseEventSequenceRef.current += 1;
            const currentEventSequence = sseEventSequenceRef.current;
            let rpcResponse: SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;

            try {
                rpcResponse = JSON.parse(event.data) as SendStreamingMessageSuccessResponse | JSONRPCErrorResponse;
            } catch (error: unknown) {
                console.error("Failed to parse SSE message:", error);
                addNotification("Received unparseable agent update.", "error");
                return;
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
            let artifactToProcess: TaskArtifactUpdateEvent["artifact"] | undefined;
            let currentTaskIdFromResult: string | undefined;

            // Determine event type and extract relevant data
            switch (result.kind) {
                case "task":
                    isFinalEvent = true;
                    // For the final task object, we only use it as a signal to end the turn.
                    // The content has already been streamed via status_updates.
                    messageToProcess = undefined;
                    currentTaskIdFromResult = result.id;
                    if (result.artifacts && result.artifacts.length > 0) {
                        console.log("Final task has artifacts to process:", result.artifacts);
                    }
                    break;
                case "status-update":
                    isFinalEvent = result.final;
                    messageToProcess = result.status?.message;
                    currentTaskIdFromResult = result.taskId;
                    break;
                case "artifact-update":
                    artifactToProcess = result.artifact;
                    currentTaskIdFromResult = result.taskId;
                    break;
                default:
                    console.warn("Received unknown result kind in SSE message:", result);
                    return;
            }

            // Process the parts of the message
            const newContentParts: Part[] = [];
            const newFileAttachments: FileAttachment[] = [];
            let agentStatusText: string | null = null;

            if (messageToProcess?.parts) {
                for (const part of messageToProcess.parts) {
                    if (part.kind === "data") {
                        const data = part.data;
                        if (data && typeof data === "object" && "type" in data) {
                            switch (data.type) {
                                case "agent_progress_update":
                                    agentStatusText = String(data?.status_text ?? "Processing...");
                                    break;
                                case "artifact_creation_progress":
                                    agentStatusText = `Saving artifact: ${String(data?.filename ?? "unknown file")} (${Number(data?.bytes_saved ?? 0)} bytes)`;
                                    break;
                                case "tool_invocation_start":
                                    break;
                                default:
                                    newContentParts.push(part);
                            }
                        }
                    } else if (part.kind === "file") {
                        const filePart = part as FilePart;
                        const fileInfo = filePart.file;
                        const attachment: FileAttachment = {
                            name: fileInfo.name || "untitled_file",
                            mime_type: fileInfo.mimeType,
                        };
                        if ("bytes" in fileInfo && fileInfo.bytes) {
                            attachment.content = fileInfo.bytes;
                        } else if ("uri" in fileInfo && fileInfo.uri) {
                            attachment.uri = fileInfo.uri;
                        }
                        newFileAttachments.push(attachment);
                    } else {
                        newContentParts.push(part);
                    }
                }
            }

            if (agentStatusText) {
                latestStatusText.current = agentStatusText;
            }

            // Update UI state based on processed parts
            setMessages(prevMessages => {
                const newMessages = [...prevMessages];
                let lastMessage = newMessages[newMessages.length - 1];

                // Remove old status bubble
                if (lastMessage?.isStatusBubble) {
                    newMessages.pop();
                    lastMessage = newMessages[newMessages.length - 1];
                }

                const textPartFromStream = newContentParts.find(p => p.kind === "text") as TextPart | undefined;
                const otherContentParts = newContentParts.filter(p => p.kind !== "text");

                // Check if we can append to the last message
                if (lastMessage && !lastMessage.isUser && !lastMessage.isComplete && lastMessage.taskId === (result as TaskStatusUpdateEvent).taskId && (textPartFromStream || newFileAttachments.length > 0)) {
                    const updatedMessage: MessageFE = {
                        ...lastMessage,
                        parts: [...lastMessage.parts],
                        files: lastMessage.files ? [...lastMessage.files] : [],
                        isComplete: isFinalEvent || newFileAttachments.length > 0,
                        metadata: {
                            ...lastMessage.metadata,
                            lastProcessedEventSequence: currentEventSequence,
                        },
                    };

                    if (textPartFromStream) {
                        const lastPart = updatedMessage.parts[updatedMessage.parts.length - 1];
                        if (lastPart?.kind === "text") {
                            updatedMessage.parts[updatedMessage.parts.length - 1] = { ...lastPart, text: lastPart.text + textPartFromStream.text };
                        } else {
                            updatedMessage.parts.push(textPartFromStream);
                        }
                    }

                    if (otherContentParts.length > 0) {
                        updatedMessage.parts.push(...otherContentParts);
                    }

                    if (newFileAttachments.length > 0) {
                        updatedMessage.files!.push(...newFileAttachments);
                    }

                    newMessages[newMessages.length - 1] = updatedMessage;
                } else {
                    // Only create a new bubble if there is visible content to render.
                    const hasVisibleContent = newContentParts.some(p => p.kind === "text" && p.text.trim());
                    if (hasVisibleContent || newFileAttachments.length > 0 || artifactToProcess) {
                        const newBubble: MessageFE = {
                            role: "agent",
                            parts: newContentParts,
                            files: newFileAttachments.length > 0 ? newFileAttachments : undefined,
                            taskId: (result as TaskStatusUpdateEvent).taskId,
                            isUser: false,
                            isComplete: isFinalEvent || newFileAttachments.length > 0,
                            metadata: {
                                messageId: rpcResponse.id?.toString() || `msg-${v4()}`,
                                sessionId: (result as TaskStatusUpdateEvent).contextId,
                                lastProcessedEventSequence: currentEventSequence,
                            },
                        };
                        if (artifactToProcess) {
                            newBubble.artifactNotification = { name: artifactToProcess.name || artifactToProcess.artifactId };
                        }
                        newMessages.push(newBubble);
                    }
                }

                // Add a new status bubble if the task is not over
                if (!isFinalEvent && latestStatusText.current) {
                    newMessages.push({
                        role: "agent",
                        parts: [{ kind: "text", text: latestStatusText.current }],
                        taskId: (result as TaskStatusUpdateEvent).taskId,
                        isUser: false,
                        isStatusBubble: true,
                        isComplete: false,
                        metadata: {
                            messageId: `status-${v4()}`,
                            lastProcessedEventSequence: currentEventSequence,
                        },
                    });
                } else if (isFinalEvent) {
                    latestStatusText.current = null;
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
                    addNotification("Task successfully cancelled.");
                    if (cancelTimeoutRef.current) clearTimeout(cancelTimeoutRef.current);
                    setIsCancelling(false);
                }

                // Save complete task when agent response is done (Step 10.5-10.9)
                if (currentTaskIdFromResult && sessionId) {
                    // Gather all messages for this task, filtering out status bubbles
                    setMessages(currentMessages => {
                        const taskMessages = currentMessages.filter(msg => msg.taskId === currentTaskIdFromResult && !msg.isStatusBubble);

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

                            // Save complete task (don't wait for completion)
                            saveTaskToBackend({
                                task_id: currentTaskIdFromResult,
                                user_message: userMessageText,
                                message_bubbles: messageBubbles,
                                task_metadata: {
                                    schema_version: CURRENT_SCHEMA_VERSION,
                                    status: taskStatus,
                                    agent_name: selectedAgentName,
                                },
                            });
                        }

                        return currentMessages;
                    });
                }

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
        [addNotification, closeCurrentEventSource, artifactsRefetch, sessionId, selectedAgentName, saveTaskToBackend, serializeMessageBubble]
    );

    const handleNewSession = useCallback(async () => {
        const log_prefix = "ChatProvider.handleNewSession:";
        console.log(`${log_prefix} Starting new session process...`);

        closeCurrentEventSource();

        if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
            console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
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

        if (cancelTimeoutRef.current) {
            clearTimeout(cancelTimeoutRef.current);
            cancelTimeoutRef.current = null;
        }
        setIsCancelling(false);

        // Reset frontend state - session will be created lazily when first message is sent
        console.log(`${log_prefix} Resetting session state - new session will be created when first message is sent`);

        // Clear session ID and name - will be set when first message is sent
        setSessionId("");
        setSessionName(null);

        setSelectedAgentName("");
        setMessages([]);
        setUserInput("");
        setIsResponding(false);
        setCurrentTaskId(null);
        setTaskIdInSidePanel(null);
        setPreviewArtifact(null);
        isFinalizing.current = false;
        latestStatusText.current = null;
        sseEventSequenceRef.current = 0;

        // Refresh artifacts (should be empty for new session)
        console.log(`${log_prefix} Refreshing artifacts for new session...`);
        await artifactsRefetch();

        // Success notification
        addNotification("New session started successfully.");
        console.log(`${log_prefix} New session setup complete - session will be created on first message.`);

        // Note: No session events dispatched here since no session exists yet.
        // Session creation event will be dispatched when first message creates the actual session.
    }, [apiPrefix, isResponding, currentTaskId, selectedAgentName, isCancelling, addNotification, artifactsRefetch, closeCurrentEventSource]);

    const handleSwitchSession = useCallback(
        async (newSessionId: string) => {
            const log_prefix = "ChatProvider.handleSwitchSession:";
            console.log(`${log_prefix} Switching to session ${newSessionId}...`);

            closeCurrentEventSource();

            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
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

            if (cancelTimeoutRef.current) {
                clearTimeout(cancelTimeoutRef.current);
                cancelTimeoutRef.current = null;
            }
            setIsCancelling(false);

            try {
                // Load session tasks instead of old message history
                await loadSessionTasks(newSessionId);

                // Load session metadata (name)
                const sessionResponse = await authenticatedFetch(`${apiPrefix}/sessions/${newSessionId}`);
                if (sessionResponse.ok) {
                    const session = await sessionResponse.json();
                    setSessionName(session?.data?.name ?? "N/A");
                }

                // Update session state
                setSessionId(newSessionId);
                setUserInput("");
                setIsResponding(false);
                setCurrentTaskId(null);
                setTaskIdInSidePanel(null);
                setPreviewArtifact(null);
                isFinalizing.current = false;
                latestStatusText.current = null;
                sseEventSequenceRef.current = 0;
            } catch (error) {
                console.error(`${log_prefix} Failed to fetch session history:`, error);
                addNotification("Error switching session. Please try again.", "error");
            }
        },
        [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, apiPrefix, addNotification, loadSessionTasks]
    );

    const updateSessionName = useCallback(
        async (sessionId: string, newName: string, showNotification: boolean = true) => {
            if (!persistenceEnabled) return;

            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}`, {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: newName }),
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Failed to update session name" }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }

                // Only show notification if explicitly requested
                if (showNotification) {
                    addNotification("Session name updated successfully.");
                }

                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                addNotification(`Error updating session name: ${error instanceof Error ? error.message : "Unknown error"}`);
            }
        },
        [apiPrefix, persistenceEnabled, addNotification]
    );

    const deleteSession = useCallback(
        async (sessionIdToDelete: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionIdToDelete}`, {
                    method: "DELETE",
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Failed to delete session" }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification("Session deleted successfully.");
                if (sessionIdToDelete === sessionId) {
                    handleNewSession();
                }
                // Trigger session list refresh
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                addNotification(`Error deleting session: ${error instanceof Error ? error.message : "Unknown error"}`);
            }
        },
        [apiPrefix, addNotification, handleNewSession, sessionId]
    );

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
            addNotification("No active task to cancel.");
            return;
        }
        if (isCancelling) {
            addNotification("Cancellation already in progress.");
            return;
        }

        addNotification(`Requesting cancellation for task ${currentTaskId}...`);
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
                    addNotification(`Cancellation for task ${currentTaskId} timed out. Allowing new input.`);
                    setIsCancelling(false);
                    setIsResponding(false);
                    closeCurrentEventSource();
                    setCurrentTaskId(null);
                    cancelTimeoutRef.current = null;

                    setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
                }, 15000);
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Unknown cancellation error" }));
                addNotification(`Failed to request cancellation: ${errorData.detail || response.statusText}`);
                setIsCancelling(false);
            }
        } catch (error) {
            addNotification(`Error sending cancellation request: ${error instanceof Error ? error.message : "Network error"}`);
            setIsCancelling(false);
        }
    }, [isResponding, isCancelling, currentTaskId, apiPrefix, addNotification, closeCurrentEventSource]);

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
                addNotification("Failed to submit feedback. Please try again.", "error");
                // Re-throw to allow UI to handle the error if needed
                throw error;
            }
        },
        [sessionId, addNotification]
    );

    const handleSseOpen = useCallback(() => {
        /* console.log for SSE open */
    }, []);

    const handleSseError = useCallback(() => {
        if (isResponding && !isFinalizing.current && !isCancellingRef.current) {
            addNotification("Connection error with agent updates.");
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
    }, [addNotification, closeCurrentEventSource, isResponding]);

    const handleSubmit = useCallback(
        async (event: FormEvent, files?: File[] | null, userInputOverride?: string | null) => {
            event.preventDefault();
            const currentInput = userInputOverride?.trim() || userInput.trim();
            const currentFiles = files || [];

            if ((!currentInput && currentFiles.length === 0) || isResponding || isCancelling || !selectedAgentName) {
                if (!selectedAgentName) addNotification("Please select an agent first.");
                if (isCancelling) addNotification("Cannot send new message while a task is being cancelled.");
                return;
            }

            closeCurrentEventSource();
            isFinalizing.current = false;
            setIsResponding(true);
            setCurrentTaskId(null);
            latestStatusText.current = null;
            sseEventSequenceRef.current = 0;

            const isNewSession = !sessionId;
            let effectiveSessionId = sessionId || undefined;

            const userMsg: MessageFE = {
                role: "user",
                parts: [{ kind: "text", text: currentInput }],
                isUser: true,
                uploadedFiles: currentFiles.length > 0 ? currentFiles : undefined,
                metadata: {
                    messageId: `msg-${v4()}`,
                    sessionId: effectiveSessionId,
                    lastProcessedEventSequence: 0,
                },
            };

            latestStatusText.current = "Thinking";
            setMessages(prev => [...prev, userMsg]);
            setUserInput("");

            const errors: string[] = [];

            try {
                // 1. Process files using hybrid approach
                // For new sessions, process sequentially to ensure all files use the same session
                // For existing sessions, process in parallel for better performance
                const uploadedFileParts: FilePart[] = [];

                if (isNewSession) {
                    // Sequential processing for new sessions
                    for (const file of currentFiles) {
                        if (file.size < INLINE_FILE_SIZE_LIMIT_BYTES) {
                            const base64Content = await fileToBase64(file);
                            uploadedFileParts.push({ kind: "file", file: { bytes: base64Content, name: file.name, mimeType: file.type } });
                        } else {
                            const uploadResult = await uploadArtifactFile(file, effectiveSessionId);
                            if (uploadResult) {
                                // Capture session ID from first upload
                                if (!effectiveSessionId && uploadResult.sessionId) {
                                    effectiveSessionId = uploadResult.sessionId;
                                    console.log(`Session created via artifact upload: ${effectiveSessionId}`);
                                }
                                uploadedFileParts.push({ kind: "file", file: { uri: uploadResult.uri, name: file.name, mimeType: file.type } });
                            } else {
                                errors.push(`Failed to upload large file: ${file.name}`);
                                addNotification(`Failed to upload large file: ${file.name}`, "error");
                            }
                        }
                    }
                } else {
                    // Parallel processing for existing sessions
                    const filePartsPromises = currentFiles.map(async (file): Promise<FilePart | null> => {
                        if (file.size < INLINE_FILE_SIZE_LIMIT_BYTES) {
                            const base64Content = await fileToBase64(file);
                            return { kind: "file", file: { bytes: base64Content, name: file.name, mimeType: file.type } };
                        } else {
                            const uploadResult = await uploadArtifactFile(file, effectiveSessionId);
                            if (uploadResult) {
                                return { kind: "file", file: { uri: uploadResult.uri, name: file.name, mimeType: file.type } };
                            } else {
                                errors.push(`Failed to upload large file: ${file.name}`);
                                addNotification(`Failed to upload large file: ${file.name}`, "error");
                                return null;
                            }
                        }
                    });
                    const results = await Promise.all(filePartsPromises);
                    uploadedFileParts.push(...results.filter((p): p is FilePart => p !== null));
                }

                // If we created a session via artifact upload, update the session state
                if (isNewSession && effectiveSessionId && effectiveSessionId !== sessionId) {
                    setSessionId(effectiveSessionId);
                    console.log(`Session created via artifact upload: ${effectiveSessionId}`);
                }

                // 2. Construct message parts
                const messageParts: Part[] = [];
                if (currentInput) {
                    messageParts.push({ kind: "text", text: currentInput });
                }
                if (errors.length > 0) {
                    messageParts.push({ kind: "text", text: `\nNote: Some files failed to upload:\n- ${errors.join("\n- ")}` });
                }
                messageParts.push(...uploadedFileParts);

                if (messageParts.length === 0) {
                    throw new Error("Cannot send an empty message.");
                }

                // 3. Construct the A2A message
                const a2aMessage: Message = {
                    role: "user",
                    parts: messageParts,
                    messageId: `msg-${v4()}`,
                    kind: "message",
                    contextId: effectiveSessionId,
                    metadata: { agent_name: selectedAgentName },
                };

                // 4. Construct the SendStreamingMessageRequest
                const sendMessageRequest: SendStreamingMessageRequest = {
                    jsonrpc: "2.0",
                    id: `req-${v4()}`,
                    method: "message/stream",
                    params: { message: a2aMessage },
                };

                // 5. Send the request
                const response = await authenticatedFetch(`${apiPrefix}/message:stream`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(sendMessageRequest),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                const result = await response.json();
                const task = result?.result as Task | undefined;
                const taskId = task?.id;
                const responseSessionId = (task as Task & { contextId?: string })?.contextId;

                if (!taskId) {
                    throw new Error("Backend did not return a valid taskId.");
                }

                if (responseSessionId && responseSessionId !== effectiveSessionId) {
                    if (effectiveSessionId) {
                        console.warn(`Backend returned a different session ID (${responseSessionId}) than expected (${effectiveSessionId}). Updating to: ${responseSessionId}`);
                    } else {
                        console.log(`Backend created new session: ${responseSessionId}`);
                    }
                    setSessionId(responseSessionId);
                    effectiveSessionId = responseSessionId;
                }

                // Save initial task with user message (Step 10.2-10.3)
                if (effectiveSessionId) {
                    await saveTaskToBackend({
                        task_id: taskId,
                        user_message: currentInput,
                        message_bubbles: [serializeMessageBubble(userMsg)],
                        task_metadata: {
                            schema_version: CURRENT_SCHEMA_VERSION,
                            status: "pending",
                            agent_name: selectedAgentName,
                        },
                    });
                }

                // If it was a new session, generate and persist its name.
                if (isNewSession && responseSessionId) {
                    const textParts = userMsg.parts.filter(p => p.kind === "text") as TextPart[];
                    const combinedText = textParts
                        .map(p => p.text)
                        .join(" ")
                        .trim();
                    if (combinedText) {
                        const newSessionName = combinedText.length > 100 ? `${combinedText.substring(0, 100)}...` : combinedText;
                        setSessionName(newSessionName);
                        updateSessionName(responseSessionId, newSessionName, false);
                    }
                    if (typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                }

                setCurrentTaskId(taskId);
                setTaskIdInSidePanel(taskId);

                // Update user message with taskId so it's included in final save
                setMessages(prev => prev.map(msg => (msg.metadata?.messageId === userMsg.metadata?.messageId ? { ...msg, taskId: taskId } : msg)));
            } catch (error) {
                addNotification(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
                setIsResponding(false);
                setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
                setCurrentTaskId(null);
                isFinalizing.current = false;
                latestStatusText.current = null;
            }
        },
        [sessionId, userInput, isResponding, isCancelling, selectedAgentName, closeCurrentEventSource, addNotification, apiPrefix, uploadArtifactFile, updateSessionName, saveTaskToBackend, serializeMessageBubble]
    );

    useEffect(() => {
        if (!selectedAgentName && agents.length > 0 && messages.length === 0) {
            const selectedAgent = agents.find(agent => agent.name === "OrchestratorAgent") ?? agents[0];
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
    }, [agents, configWelcomeMessage, messages.length, selectedAgentName, sessionId]);

    useEffect(() => {
        if (currentTaskId && apiPrefix) {
            console.log(`ChatProvider Effect: currentTaskId is ${currentTaskId}. Setting up EventSource.`);
            const accessToken = getAccessToken();
            const eventSourceUrl = `${apiPrefix}/sse/subscribe/${currentTaskId}${accessToken ? `?token=${accessToken}` : ""}`;
            const eventSource = new EventSource(eventSourceUrl, { withCredentials: true });
            currentEventSource.current = eventSource;

            eventSource.onopen = handleSseOpen;
            eventSource.onerror = handleSseError;
            eventSource.addEventListener("status_update", handleSseMessage);
            eventSource.addEventListener("artifact_update", handleSseMessage);
            eventSource.addEventListener("final_response", handleSseMessage);
            eventSource.addEventListener("error", handleSseMessage);

            return () => {
                console.log(`ChatProvider Effect Cleanup: currentTaskId was ${currentTaskId}. Closing EventSource.`);
                // Explicitly remove listeners before closing
                eventSource.removeEventListener("status_update", handleSseMessage);
                eventSource.removeEventListener("artifact_update", handleSseMessage);
                eventSource.removeEventListener("final_response", handleSseMessage);
                eventSource.removeEventListener("error", handleSseMessage);
                closeCurrentEventSource();
            };
        } else {
            console.log(`ChatProvider Effect: currentTaskId is null or apiPrefix missing. Ensuring EventSource is closed.`);
            closeCurrentEventSource();
        }
    }, [currentTaskId, apiPrefix, handleSseMessage, handleSseOpen, handleSseError, closeCurrentEventSource]);

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
        userInput,
        setUserInput,
        isResponding,
        currentTaskId,
        isCancelling,
        latestStatusText,
        agents,
        agentsLoading,
        agentsError,
        agentsRefetch,
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
        openMessageAttachmentForPreview,
        previewArtifact,
        setPreviewArtifact,
        updateSessionName,
        deleteSession,
    };

    return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};
