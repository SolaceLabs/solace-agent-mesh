import React, { useState, useCallback, useEffect, useRef, type FormEvent, type ReactNode } from "react";

import { useConfigContext, useArtifacts, useAgents } from "@/lib/hooks";
import { authenticatedFetch, getAccessToken } from "@/lib/utils/api";
import { ChatContext, type ChatContextValue } from "@/lib/contexts";
import type { ArtifactInfo, CancelTaskRequest, FileAttachment, FilePart, JSONRPCErrorResponse, Message, MessageFE, Notification, Part, SendStreamingMessageRequest, SendStreamingMessageSuccessResponse, Session, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TextPart } from "@/lib/types";

interface ChatProviderProps {
    children: ReactNode;
}

interface HistoryMessage {
    id: string;
    message: string;
    sender_type: "user" | "llm";
    session_id: string;
    created_at: string;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, configServerUrl } = useConfigContext();
    const apiPrefix = `${configServerUrl}/api/v1`;

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
    const [userInput, setUserInput] = useState<string>("");
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const currentEventSource = useRef<EventSource | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false); // New state for cancellation
    const isCancellingRef = useRef(isCancelling);
    useEffect(() => {
        isCancellingRef.current = isCancelling;
    }, [isCancelling]);
    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null); // Ref for cancel timeout
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);

    // Agents State
    const {
        agents,
        error: agentsError,
        isLoading: agentsLoading,
        refetch: agentsRefetch,
    } = useAgents();

    // Chat Side Panel State
    const {
        artifacts,
        isLoading: artifactsLoading,
        refetch: artifactsRefetch,
    } = useArtifacts(sessionId);

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


    const getHistory = useCallback(
        async (sessionId: string) => {
            const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}/messages`);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Failed to fetch session history" }));
                throw new Error(errorData.detail || `HTTP error ${response.status}`);
            }
            return response.json();
        },
        [apiPrefix]
    );

    const uploadArtifactFile = useCallback(
        async (file: File): Promise<string | null> => {
            const formData = new FormData();
            formData.append("file", file);
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}/${encodeURIComponent(file.name)}`, {
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
                return result.uri || null;
            } catch (error) {
                addNotification(`Error uploading artifact "${file.name}": ${error instanceof Error ? error.message : "Unknown error"}`);
                return null;
            }
        },
        [apiPrefix, addNotification, artifactsRefetch]
    );

    const [sessionName, setSessionName] = useState<string | null>(null);
    // Note: Other state variables are already declared above (lines 36-52)

    const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null);

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
        [apiPrefix, addNotification, artifactsRefetch]
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
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(filename)}`, {
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
    }, [selectedArtifactFilenames, apiPrefix, addNotification, artifactsRefetch]);

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
        [apiPrefix, addNotification, artifacts]
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
        [apiPrefix, addNotification, artifacts, previewedArtifactAvailableVersions]
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
                console.log("TEST-SSE ChatProvider Raw Message:", event.data);
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
                if (
                    lastMessage &&
                    !lastMessage.isUser &&
                    !lastMessage.isComplete &&
                    lastMessage.taskId === (result as TaskStatusUpdateEvent).taskId &&
                    (textPartFromStream || newFileAttachments.length > 0)
                ) {
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
                                messageId: rpcResponse.id?.toString() || `msg-${crypto.randomUUID()}`,
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
                            messageId: `status-${crypto.randomUUID()}`,
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
        [addNotification, closeCurrentEventSource, artifactsRefetch]
    );

    const handleNewSession = useCallback(async () => {
        const log_prefix = "ChatProvider.handleNewSession:";
        console.log(`${log_prefix} Starting new session process...`);

        closeCurrentEventSource();

        if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
            console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
            try {
                authenticatedFetch(`${apiPrefix}/tasks/cancel`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        agent_name: selectedAgentName,
                        task_id: currentTaskId,
                    }),
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

        // Reset UI state with empty session ID
        const welcomeMessages: MessageFE[] = configWelcomeMessage
            ? [
                {
                    parts: [{ kind: "text", text: configWelcomeMessage }],
                    isUser: false,
                    isComplete: true,
                    role: "agent",
                    metadata: {
                        sessionId: "", // Empty - will be populated when session is created
                        lastProcessedEventSequence: 0,
                    },
                },
            ]
            : [];

        setMessages(welcomeMessages);
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
    }, [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, configWelcomeMessage, addNotification, artifactsRefetch]);

    const handleSwitchSession = useCallback(
        async (newSessionId: string) => {
            const log_prefix = "ChatProvider.handleSwitchSession:";
            console.log(`${log_prefix} Switching to session ${newSessionId}...`);

            closeCurrentEventSource();

            if (isResponding && currentTaskId && selectedAgentName && !isCancelling) {
                console.log(`${log_prefix} Cancelling current task ${currentTaskId}`);
                try {
                    await authenticatedFetch(`${apiPrefix}/tasks/cancel`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            agent_name: selectedAgentName,
                            task_id: currentTaskId,
                        }),
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
                const history = await getHistory(newSessionId);
                const formattedMessages: MessageFE[] = history.map((msg: HistoryMessage) => ({
                    parts: [{ kind: "text", text: msg.message }],
                    isUser: msg.sender_type === "user",
                    isComplete: true,
                    role: msg.sender_type === "user" ? "user" : "agent",
                    metadata: {
                        sessionId: msg.session_id,
                        messageId: msg.id,
                        lastProcessedEventSequence: 0,
                    },
                }));
    
                const sessionResponse = await authenticatedFetch(`${apiPrefix}/sessions/${newSessionId}`);
                if (sessionResponse.ok) {
                    const sessionData = await sessionResponse.json();
                    setSessionName(sessionData.name);
                }
    
                setSessionId(newSessionId);
                setMessages(formattedMessages);
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
        [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, apiPrefix, addNotification, getHistory]
    );

    const updateSessionName = useCallback(
        async (sessionId: string, newName: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: newName }),
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Failed to update session name' }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification('Session name updated successfully.');
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                addNotification(`Error updating session name: ${error instanceof Error ? error.message : 'Unknown error'}`);
            }
        },
        [apiPrefix, addNotification]
    );

    const deleteSession = useCallback(
        async (sessionIdToDelete: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/sessions/${sessionIdToDelete}`, {
                    method: 'DELETE',
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Failed to delete session' }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification('Session deleted successfully.');
                if (sessionIdToDelete === sessionId) {
                    handleNewSession();
                }
                // Trigger session list refresh
                if (typeof window !== "undefined") {
                    window.dispatchEvent(new CustomEvent("new-chat-session"));
                }
            } catch (error) {
                addNotification(`Error deleting session: ${error instanceof Error ? error.message : 'Unknown error'}`);
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
            console.log("handleSubmit: using sessionId", sessionId);
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
            setUserInput("");
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
                        const uri = await uploadArtifactFile(file);
                        if (uri) {
                            return {
                                kind: "file",
                                file: {
                                    uri: uri,
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

                const uploadedFileParts = (await Promise.all(filePartsPromises)).filter(
                    (p): p is FilePart => p !== null
                );

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
                        agent_name: selectedAgentName, // For gateway routing
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
                    setMessages(prev => prev.map(msg => 
                        msg.metadata?.messageId === userMsg.metadata?.messageId 
                            ? { ...msg, metadata: { ...msg.metadata, sessionId: responseSessionId } }
                            : msg
                    ));
                    
                    // Trigger session list refresh for new sessions
                    if (isNewSession && typeof window !== "undefined") {
                        window.dispatchEvent(new CustomEvent("new-chat-session"));
                    }
                }

                console.log(`ChatProvider handleSubmit: Received taskId ${taskId}. Setting currentTaskId and taskIdInSidePanel.`);
                setCurrentTaskId(taskId);
                setTaskIdInSidePanel(taskId);
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
        [userInput, isResponding, isCancelling, sessionId, selectedAgentName, apiPrefix, addNotification, closeCurrentEventSource, uploadArtifactFile]
    );

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
