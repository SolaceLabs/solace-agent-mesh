/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState, useCallback, useEffect, useRef, useMemo, type FormEvent, type ReactNode } from "react";
import { v4 } from "uuid";

import { useConfigContext, useArtifacts, useAgentCards } from "@/lib/hooks";
import { useProjectContext, registerProjectDeletedCallback } from "@/lib/providers";
import type { Project } from "@/lib/types/projects";

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

import { authenticatedFetch, getAccessToken, submitFeedback } from "@/lib/utils/api";
import { ChatContext, type ChatContextValue } from "@/lib/contexts";
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
} from "@/lib/types";

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, configServerUrl, persistenceEnabled, configCollectFeedback } = useConfigContext();
    const apiPrefix = useMemo(() => `${configServerUrl}/api/v1`, [configServerUrl]);
    const { activeProject, setActiveProject, projects } = useProjectContext();

    const INLINE_FILE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024; // 1 MB

    const fileToBase64 = (file: File): Promise<string> =>
        new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve((reader.result as string).split(",")[1]);
            reader.onerror = error => reject(error);
        });

    // State Variables from useChat
    const [sessionId, setSessionId] = useState<string>("");
    const [messages, setMessages] = useState<MessageFE[]>([]);
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const currentEventSource = useRef<EventSource | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false); // New state for cancellation
    const isCancellingRef = useRef(isCancelling);
    const savingTasksRef = useRef<Set<string>>(new Set());
    // Track in-flight artifact preview fetches to prevent duplicates
    const artifactFetchInProgressRef = useRef<Set<string>>(new Set());
    const artifactDownloadInProgressRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        isCancellingRef.current = isCancelling;
    }, [isCancelling]);
    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null); // Ref for cancel timeout
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);

    // Agents State
    const { agents, error: agentsError, isLoading: agentsLoading, refetch: agentsRefetch } = useAgentCards();

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
    const serializeMessageBubble = useCallback((message: MessageFE) => {
        const textParts = message.parts?.filter(p => p.kind === "text") as TextPart[] | undefined;
        const combinedText = textParts?.map(p => p.text).join("") || "";

        return {
            id: message.metadata?.messageId || `msg-${crypto.randomUUID()}`,
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
        async (taskData: { task_id: string; user_message?: string; message_bubbles: any[]; task_metadata?: any }) => {
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
        (task: { taskId: string; messageBubbles: any[]; taskMetadata?: any; createdTime: number }): MessageFE[] => {
            return task.messageBubbles.map(bubble => ({
                taskId: task.taskId,
                role: bubble.type === "user" ? "user" : "agent",
                parts: bubble.parts || [{ kind: "text", text: bubble.text || "" }],
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
            }));
        },
        [sessionId]
    );

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
            const effectiveSessionId = overrideSessionId || sessionId;
            const formData = new FormData();
            formData.append("file", file);
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${effectiveSessionId}/${encodeURIComponent(file.name)}`, {
                    method: "POST",
                    body: formData,
                    credentials: "include",
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: `Failed to upload ${file.name}` }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                const result = await response.json();
                addNotification(`Artifact "${file.name}" uploaded successfully.`);
                await artifactsRefetch();
                return result.uri ? { uri: result.uri, sessionId: effectiveSessionId } : null;
            } catch (error) {
                addNotification(`Error uploading artifact "${file.name}": ${error instanceof Error ? error.message : "Unknown error"}`);
                return null;
            }
        },
        [apiPrefix, sessionId, addNotification, artifactsRefetch]
    );

    // Session State
    const [sessionName, setSessionName] = useState<string | null>(null);
    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);
    const [isLoadingSession, setIsLoadingSession] = useState<boolean>(false);

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

                const versionsResponse = await authenticatedFetch(versionsUrl, { credentials: "include" });
                if (!versionsResponse.ok) throw new Error("Error fetching version list");
                const availableVersions: number[] = await versionsResponse.json();
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

                const contentResponse = await authenticatedFetch(contentUrl, { credentials: "include" });
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
            } finally {
                // Remove from in-progress set immediately when done
                artifactFetchInProgressRef.current.delete(artifactFilename);
            }
        },
        [apiPrefix, sessionId, activeProject?.id, artifacts, addNotification, previewArtifactFilename]
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
                addNotification(`Version ${targetVersion} is not available for ${artifactFilename}.`);
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

                const contentResponse = await authenticatedFetch(contentUrl, { credentials: "include" });
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
        [apiPrefix, addNotification, artifacts, previewedArtifactAvailableVersions, sessionId, activeProject?.id]
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
                const versionsResponse = await authenticatedFetch(
                    `${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions`,
                    { credentials: "include" }
                );
                if (!versionsResponse.ok) throw new Error("Error fetching version list");

                const availableVersions: number[] = await versionsResponse.json();
                if (!availableVersions || availableVersions.length === 0) {
                    throw new Error("No versions available");
                }

                const latestVersion = Math.max(...availableVersions);
                const contentResponse = await authenticatedFetch(
                    `${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(filename)}/versions/${latestVersion}`,
                    { credentials: "include" }
                );
                if (!contentResponse.ok) throw new Error("Error fetching artifact content");

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
                console.error(`Error downloading artifact ${filename}:`, error);
                addNotification(
                    `Error downloading artifact: ${error instanceof Error ? error.message : "Unknown error"}`,
                    "error"
                );
                return null;
            } finally {
                // Remove from in-progress set immediately when done
                artifactDownloadInProgressRef.current.delete(filename);
            }
        },
        [apiPrefix, sessionId, artifacts, addNotification, setArtifacts]
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
                            messageId: `msg-${crypto.randomUUID()}`,
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
                                                gatewayTaskId: gateway_task_id
                                            },
                                            isUser: false,
                                            isComplete: true,
                                            metadata: { messageId: `auth-${v4()}` }
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
                                messageId: rpcResponse.id?.toString() || `msg-${crypto.randomUUID()}`,
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

                // Mark all in-progress artifacts as completed when task finishes
                setMessages(currentMessages => {
                    return currentMessages.map(msg => {
                        if (msg.isUser) return msg;

                        const hasInProgressArtifacts = msg.parts.some(
                            p => p.kind === "artifact" && (p as ArtifactPart).status === "in-progress"
                        );

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
        [addNotification, closeCurrentEventSource, artifactsRefetch, sessionId, selectedAgentName, saveTaskToBackend, serializeMessageBubble, downloadAndResolveArtifact, setArtifacts]
    );

    const handleNewSession = useCallback(async (preserveProjectContext: boolean = false) => {
        const log_prefix = "ChatProvider.handleNewSession:";
        
        closeCurrentEventSource();

        if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
            try {
                const cancelRequest = {
                    jsonrpc: "2.0",
                    id: `req-${crypto.randomUUID()}`,
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
        // Success notification
        addNotification("New session started successfully.");
        
        // Dispatch event to focus chat input
        if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("focus-chat-input"));
        }
        
        // Note: No session events dispatched here since no session exists yet.
        // Session creation event will be dispatched when first message creates the actual session.
    }, [apiPrefix, isResponding, currentTaskId, selectedAgentName, isCancelling, addNotification, closeCurrentEventSource, activeProject, setActiveProject, setPreviewArtifact]);

    const handleSwitchSession = useCallback(
        async (newSessionId: string) => {
            const log_prefix = "ChatProvider.handleSwitchSession:";
            console.log(`${log_prefix} Switching to session ${newSessionId}...`);

            setIsLoadingSession(true);
            
            // Clear messages immediately to prevent showing old session's messages
            setMessages([]);
            
            closeCurrentEventSource();

            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
                try {
                    const cancelRequest = {
                        jsonrpc: "2.0",
                        id: `req-${crypto.randomUUID()}`,
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
                // Load session metadata first to get project info
                const sessionResponse = await authenticatedFetch(`${apiPrefix}/sessions/${newSessionId}`);
                let session: Session | null = null;
                if (sessionResponse.ok) {
                    const sessionData = await sessionResponse.json();
                    session = sessionData?.data;
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
                }

                // Update session state
                setSessionId(newSessionId);
                setIsResponding(false);
                setCurrentTaskId(null);
                setTaskIdInSidePanel(null);
                setPreviewArtifact(null);
                isFinalizing.current = false;
                latestStatusText.current = null;
                sseEventSequenceRef.current = 0;

                // Load session tasks
                await loadSessionTasks(newSessionId);
            } catch (error) {
                console.error(`${log_prefix} Failed to fetch session history:`, error);
                addNotification("Error switching session. Please try again.", "error");
            } finally {
                setIsLoadingSession(false);
            }
        },
        [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, apiPrefix, addNotification, loadSessionTasks, activeProject, projects, setActiveProject, setPreviewArtifact]
    );

    const updateSessionName = useCallback(
        async (sessionId: string, newName: string) => {
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
                addNotification("Session name updated successfully.");
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                addNotification(`Error updating session name: ${error instanceof Error ? error.message : "Unknown error"}`);
            }
        },
        [apiPrefix, addNotification]
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
            return prevArtifacts.map(artifact =>
                artifact.filename === filename
                    ? { ...artifact, isDisplayed: displayed }
                    : artifact
            );
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
                id: `req-${crypto.randomUUID()}`,
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
        async (event: FormEvent, files?: File[] | null, userInputText?: string | null) => {
            event.preventDefault();
            const currentInput = userInputText?.trim() || "";
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

            const userMsg: MessageFE = {
                role: "user",
                parts: [{ kind: "text", text: currentInput }],
                isUser: true,
                uploadedFiles: currentFiles.length > 0 ? currentFiles : undefined,
                metadata: {
                    messageId: `msg-${crypto.randomUUID()}`,
                    sessionId: sessionId,
                    lastProcessedEventSequence: 0,
                },
            };
            latestStatusText.current = "Thinking";
            setMessages(prev => [...prev, userMsg]);

            try {
                // 1. Process files using hybrid approach
                const filePartsPromises = currentFiles.map(async (file): Promise<FilePart | null> => {
                    if (file.size < INLINE_FILE_SIZE_LIMIT_BYTES) {
                        // Small file: send inline as base64
                        const base64Content = await fileToBase64(file);
                        return {
                            kind: "file",
                            file: {
                                bytes: base64Content,
                                name: file.name,
                                mimeType: file.type,
                            },
                        };
                    } else {
                        // Large file: upload and get URI
                        const result = await uploadArtifactFile(file);
                        if (result) {
                            return {
                                kind: "file",
                                file: {
                                    uri: result.uri,
                                    name: file.name,
                                    mimeType: file.type,
                                },
                            };
                        } else {
                            addNotification(`Failed to upload large file: ${file.name}`, "error");
                            return null;
                        }
                    }
                });

                const uploadedFileParts = (await Promise.all(filePartsPromises)).filter((p): p is FilePart => p !== null);

                // 2. Construct message parts
                const messageParts: Part[] = [];
                if (currentInput) {
                    messageParts.push({ kind: "text", text: currentInput });
                }
                messageParts.push(...uploadedFileParts);

                if (messageParts.length === 0) {
                    throw new Error("Cannot send an empty message.");
                }

                // 3. Construct the A2A message
                console.log(`ChatProvider handleSubmit: Using sessionId for contextId: ${sessionId}`);
                const a2aMessage: Message = {
                    role: "user",
                    parts: messageParts,
                    messageId: `msg-${crypto.randomUUID()}`,
                    kind: "message",
                    contextId: sessionId,
                    metadata: {
                        agent_name: selectedAgentName,
                        project_id: activeProject?.id || null,
                    },
                };

                // 4. Construct the SendStreamingMessageRequest
                const sendMessageRequest: SendStreamingMessageRequest = {
                    jsonrpc: "2.0",
                    id: `req-${crypto.randomUUID()}`,
                    method: "message/stream",
                    params: {
                        message: a2aMessage,
                    },
                };

                // 5. Send the request
                console.log("ChatProvider handleSubmit: Sending POST to /message:stream");
                const response = await authenticatedFetch(`${apiPrefix}/message:stream`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(sendMessageRequest),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
                    console.error("ChatProvider handleSubmit: Error from /message:stream", response.status, errorData);
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                const result = await response.json();

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
                if (responseSessionId && responseSessionId !== sessionId) {
                    console.log(`ChatProvider handleSubmit: Updating sessionId from ${sessionId} to ${responseSessionId}`);
                    const isNewSession = !sessionId || sessionId === "";
                    setSessionId(responseSessionId);
                    // Update the user message metadata with the new session ID
                    setMessages(prev => prev.map(msg => (msg.metadata?.messageId === userMsg.metadata?.messageId ? { ...msg, metadata: { ...msg.metadata, sessionId: responseSessionId } } : msg)));

                    // Save initial task with user message (Step 10.2-10.3)
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

                    // If it was a new session, generate and persist its name
                    if (isNewSession) {
                        const textParts = userMsg.parts.filter(p => p.kind === "text") as TextPart[];
                        const combinedText = textParts
                            .map(p => p.text)
                            .join(" ")
                            .trim();
                        if (combinedText) {
                            const newSessionName = combinedText.length > 100 ? `${combinedText.substring(0, 100)}...` : combinedText;
                            setSessionName(newSessionName);
                            await updateSessionName(responseSessionId, newSessionName);
                        }
                    }

                    // Trigger session list refresh for new sessions
                    if (isNewSession && typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                }

                console.log(`ChatProvider handleSubmit: Received taskId ${taskId}. Setting currentTaskId and taskIdInSidePanel.`);
                setCurrentTaskId(taskId);
                setTaskIdInSidePanel(taskId);

                // Update user message with taskId so it's included in final save
                setMessages(prev => prev.map(msg => (msg.metadata?.messageId === userMsg.metadata?.messageId ? { ...msg, taskId: taskId } : msg)));
            } catch (error) {
                console.error("ChatProvider handleSubmit: Catch block error", error);
                addNotification(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
                setIsResponding(false);
                setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
                setCurrentTaskId(null);
                isFinalizing.current = false;
                latestStatusText.current = null;
            }
        },
        [sessionId, isResponding, isCancelling, selectedAgentName, closeCurrentEventSource, addNotification, apiPrefix, uploadArtifactFile, updateSessionName, saveTaskToBackend, serializeMessageBubble, INLINE_FILE_SIZE_LIMIT_BYTES, activeProject]
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
            // 1. Project's default agent (if in project context)
            // 2. OrchestratorAgent (fallback)
            // 3. First available agent
            let selectedAgent = agents[0];
            
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
            const eventSourceUrl = `${apiPrefix}/sse/subscribe/${currentTaskId}${accessToken ? `?token=${accessToken}` : ""}`;
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
        openMessageAttachmentForPreview,
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
    };

    return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};
