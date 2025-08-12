import React, { useState, useCallback, useEffect, useRef, type FormEvent, type ReactNode } from "react";

import { useConfigContext, useArtifacts } from "@/lib/hooks";
import { authenticatedFetch, getAccessToken } from "@/lib/utils/api";
import { ChatContext, type ChatContextValue } from "@/lib/contexts";
import type { ArtifactInfo, DataPart, FileAttachment, FilePart, JSONRPCError, JSONRPCResponse, MessageFE, Notification, Task, TaskArtifactUpdateEvent, TaskStatusUpdateEvent, TextPart, ToolEvent } from "@/lib/types";

interface ChatProviderProps {
    children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
    const { configWelcomeMessage, configServerUrl } = useConfigContext();
    const apiPrefix = `${configServerUrl}/api/v1`;

    // State Variables from useChat
    const [sessionId, setSessionId] = useState<string>(() => `web-session-${Date.now()}`);
    const [messages, setMessages] = useState<MessageFE[]>([]);
    const [userInput, setUserInput] = useState<string>("");
    const [isResponding, setIsResponding] = useState<boolean>(false);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    const currentEventSource = useRef<EventSource | null>(null);
    const [selectedAgentName, setSelectedAgentName] = useState<string>("");
    const [isCancelling, setIsCancelling] = useState<boolean>(false); // New state for cancellation
    const [taskIdInSidePanel, setTaskIdInSidePanel] = useState<string | null>(null);
    const cancelTimeoutRef = useRef<NodeJS.Timeout | null>(null); // Ref for cancel timeout
    const isFinalizing = useRef(false);
    const latestStatusText = useRef<string | null>(null);
    const sseEventSequenceRef = useRef<number>(0);

    // Chat Side Panel State
    const {
        artifacts,
        isLoading: artifactsLoading,
        refetch: artifactsRefetch,
        error: artifactsError,
    } = useArtifacts();

    const artifactsRefetchIfNeeded = useCallback(
        async (files: FileAttachment[]) => {
            const needsRefetch = !artifactsLoading && files?.some(file => !artifacts.some(artifact => artifact.filename === file.name));
            if (needsRefetch) {
                await artifactsRefetch();
            }
        },
        [artifacts, artifactsLoading, artifactsRefetch]
    );

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

    // Chat Side Panel Functions
    const uploadArtifactFile = useCallback(
        async (file: File) => {
            const formData = new FormData();
            formData.append("upload_file", file, file.name);
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(file.name)}`, {
                    method: "POST",
                    body: formData,
                    credentials: "include",
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: `Failed to upload ${file.name}` }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification(`Artifact "${file.name}" uploaded successfully.`);
                await artifactsRefetch();
            } catch (error) {
                addNotification(`Error uploading artifact "${file.name}": ${error instanceof Error ? error.message : "Unknown error"}`);
            }
        },
        [apiPrefix, addNotification, artifactsRefetch]
    );

    const deleteArtifactInternal = useCallback(
        async (filename: string) => {
            try {
                const response = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(filename)}`, {
                    method: "DELETE",
                    credentials: "include",
                });
                if (!response.ok && response.status !== 204) {
                    const errorData = await response.json().catch(() => ({ detail: `Failed to delete ${filename}` }));
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                addNotification(`File "${filename}" deleted successfully.`);
                await artifactsRefetch();
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
        await artifactsRefetch();
        setSelectedArtifactFilenames(new Set());
        setIsArtifactEditMode(false);
    }, [selectedArtifactFilenames, apiPrefix, addNotification, artifactsRefetch]);

    const openArtifactForPreview = useCallback(
        async (artifactFilename: string): Promise<FileAttachment | null> => {
            setPreviewedArtifactAvailableVersions(null);
            setCurrentPreviewedVersionNumber(null);
            setPreviewFileContent(null);
            try {
                const versionsResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(artifactFilename)}/versions`, { credentials: "include" });
                if (!versionsResponse.ok) throw new Error("Error fetching version list");
                const availableVersions: number[] = await versionsResponse.json();
                if (!availableVersions || availableVersions.length === 0) throw new Error("No versions available");
                setPreviewedArtifactAvailableVersions(availableVersions.sort((a, b) => a - b));
                const latestVersion = Math.max(...availableVersions);
                setCurrentPreviewedVersionNumber(latestVersion);
                const contentResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(artifactFilename)}/versions/${latestVersion}`, { credentials: "include" });
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
                const contentResponse = await authenticatedFetch(`${apiPrefix}/artifacts/${encodeURIComponent(artifactFilename)}/versions/${targetVersion}`, { credentials: "include" });
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

    // Side Panel Control Functions
    const openSidePanelTab = useCallback((tab: "files" | "workflow") => {
        setIsSidePanelCollapsed(false);
        setActiveSidePanelTab(tab);

        // Dispatch a custom event to notify ChatPage to expand the panel
        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("expand-side-panel", {
                    detail: { tab },
                })
            );
        }
    }, []);

    const handleSseMessage = useCallback(
        (event: MessageEvent) => {
            sseEventSequenceRef.current += 1;
            const currentEventSequence = sseEventSequenceRef.current;
            let parsedData: { jsonrpc: string; result: unknown; error: unknown };
            try {
                console.log("TEST-SSE ChatProvider Raw Message:", event.data);
                parsedData = JSON.parse(event.data);
            } catch (error: unknown) {
                console.error(error);
                addNotification("Received unparseable agent update.", "error");
                return;
            }

            const rpcResponse = parsedData as JSONRPCResponse;
            let messageContent = "";
            let receivedFiles: FileAttachment[] = [];
            let artifactNotificationData: MessageFE["artifactNotification"] = undefined;
            let processedAgentStatusSignal = false; // Flag to indicate if a dedicated agent status signal was handled
            let hasOtherContentParts = false; // Flag to check if there are parts other than the signal
            let errorContent: JSONRPCError | null = null;
            let currentMessageId = rpcResponse.id?.toString() || currentTaskId || `msg-${Date.now()}`;
            const isFinalResponseEvent = event.type === "final_response";
            let isFinalStatusUpdate = false;
            let isEmptyLlmResponseSignal = false; // Initialize flag
            const isErrorResponse = !!rpcResponse.error || event.type === "error";
            let currentToolEvents: ToolEvent[] = [];
            let agentStatusText: string | null = null;

            if (rpcResponse.error) {
                errorContent = rpcResponse.error;
                messageContent = `Error: ${errorContent.message}`;
            } else if (rpcResponse.result) {
                const result = rpcResponse.result as { id: string; status: TaskStatusUpdateEvent["status"]; artifact: TaskArtifactUpdateEvent["artifact"]; final?: boolean };
                if (result.id && (result.status || result.artifact)) {
                    if (result.status) {
                        const statusUpdate = result as TaskStatusUpdateEvent;
                        isFinalStatusUpdate = statusUpdate.final ?? false;
                        currentMessageId = statusUpdate.id;

                        // Check if this is a failed task (has sessionId and state is 'failed')
                        if ("sessionId" in result && statusUpdate.status.state === "failed") {
                            console.log("DEBUG: Detected failed task in status_update", statusUpdate);
                            if (statusUpdate.status.message?.parts) {
                                for (const part of statusUpdate.status.message.parts) {
                                    if (part.type === "text") {
                                        messageContent += (part as TextPart).text || "";
                                        hasOtherContentParts = true;
                                    }
                                }
                            }

                            if (!messageContent) {
                                messageContent = "An unexpected error occurred during task execution.";
                                hasOtherContentParts = true;
                            }
                            console.log("DEBUG: Failed task error message", { messageContent, hasOtherContentParts });
                            // Mark this as an error response
                            errorContent = {
                                code: -32603, // Internal error code
                                message: messageContent,
                            } as JSONRPCError;
                            console.log("DEBUG: Set errorContent for failed task", errorContent);
                        } else if (statusUpdate.status.message && statusUpdate.status.message.parts) {
                            for (const part of statusUpdate.status.message.parts) {
                                // Iterate with for...of
                                if (part.type === "data" && (part as DataPart).data?.a2a_signal_type === "agent_status_message") {
                                    processedAgentStatusSignal = true;
                                    processedAgentStatusSignal = true; // Mark that we've processed this type of signal
                                    const signalData = (part as DataPart).data;
                                    const statusText = signalData.text || "Status update received.";
                                    latestStatusText.current = statusText;
                                    continue;
                                }

                                // If not a special signal, process as other content
                                hasOtherContentParts = true;
                                if (part.type === "text") {
                                    messageContent += (part as TextPart).text || "";
                                } else if (part.type === "file") {
                                    receivedFiles.push({ name: (part as FilePart).file.name || "unknown_file", content: (part as FilePart).file.bytes || "", mime_type: (part as FilePart).file.mimeType ?? "application/octet-stream" });
                                } else if (part.type === "data") {
                                    const dataPart = part as DataPart;

                                    if (dataPart.data?.type === "agent_status" && typeof dataPart.data?.text === "string") {
                                        agentStatusText = dataPart.data.text;
                                    } else if (dataPart.metadata?.tool_name) {
                                        currentToolEvents.push({ toolName: dataPart.metadata.tool_name, data: dataPart.data });
                                    }
                                }
                            }
                        }
                    } else {
                        const artifactUpdate = result as TaskArtifactUpdateEvent;
                        currentMessageId = artifactUpdate.id;
                        const artifact = artifactUpdate.artifact;
                        artifact.parts.forEach(part => {
                            if (part.type === "file")
                                receivedFiles.push({
                                    name: (part as FilePart).file.name || artifact.name || "unknown_artifact_file",
                                    content: (part as FilePart).file.bytes || "",
                                    mime_type: (part as FilePart).file.mimeType ?? "application/octet-stream",
                                });
                            else if (part.type === "data" && part.metadata?.tool_name) currentToolEvents.push({ toolName: (part as DataPart)?.metadata?.tool_name, data: (part as DataPart).data });
                        });
                        artifactNotificationData = { name: artifact.name || "untitled", version: artifact.metadata?.version };
                        hasOtherContentParts = true;
                    }
                } else if (result.id && result.status && !("final" in result) && event.type === "final_response") {
                    // Final Task object
                    const finalTask = result as unknown as Task;
                    currentMessageId = finalTask.id;

                    // Check if the task failed and extract error message
                    if (finalTask.status?.state === "failed") {
                        if (finalTask.status.message?.parts) {
                            for (const part of finalTask.status.message.parts) {
                                if (part.type === "text") {
                                    messageContent += (part as TextPart).text || "";
                                    hasOtherContentParts = true;
                                }
                            }
                        }
                        // If no message parts found, use a default error message
                        if (!messageContent) {
                            messageContent = "An unexpected error occurred during task execution.";
                            hasOtherContentParts = true;
                        }
                        // Mark this as an error response
                        errorContent = {
                            code: -32603, // Internal error code
                            message: messageContent,
                        } as JSONRPCError;
                    } else {
                        // Reset content accumulators for successful final responses
                        messageContent = "";
                        receivedFiles = [];
                        artifactNotificationData = undefined;
                        currentToolEvents = [];
                        agentStatusText = null;
                        hasOtherContentParts = false;
                    }
                }
                // Determine if this event was an empty llm_response signal
                if (rpcResponse.result?.status && (rpcResponse.result as TaskStatusUpdateEvent).status.message?.metadata?.type === "llm_response" && !hasOtherContentParts) {
                    isEmptyLlmResponseSignal = true;
                }
            }
            if (agentStatusText) latestStatusText.current = agentStatusText;

            const isEndOfThisTurn = (isFinalStatusUpdate && !isEmptyLlmResponseSignal) || isFinalResponseEvent || isErrorResponse;

            setMessages(prevMessages => {
                let newMessages = [...prevMessages];
                const lastMessageIsStatusBubble = newMessages[newMessages.length - 1]?.isStatusBubble;
                if (lastMessageIsStatusBubble) {
                    newMessages = newMessages.slice(0, -1);
                }

                let appendedToExistingBubble = false;
                let newMainBubbleAddedByThisEvent = false;

                // Helper to add a new main content bubble and set the flag
                const addNewMainBubble = (newMessageData: Partial<MessageFE>, sequence: number) => {
                    const newMessage = { taskId: currentTaskId ?? undefined, isUser: false, isComplete: false, metadata: { sessionId, messageId: currentMessageId, lastProcessedEventSequence: sequence }, ...newMessageData }
                    newMessages.push(newMessage);
                    
                    // Ensure error messages are marked complete if they are added as new bubbles
                    if (newMessageData.text && errorContent) {
                        newMessages[newMessages.length - 1].isComplete = true;
                    }
                    newMainBubbleAddedByThisEvent = true;
                };

                const lastMsgOriginalIndex = newMessages.length - 1; // Index of last message *before* any new additions from this event

                // Only add a chat bubble if the event wasn't solely for an agent status signal
                const shouldCreateChatBubble = !processedAgentStatusSignal || hasOtherContentParts || isFinalResponseEvent || isErrorResponse;

                if (shouldCreateChatBubble) {
                    const lastMsg = newMessages.length > 0 ? newMessages[newMessages.length - 1] : null;
                    if (messageContent && !isFinalResponseEvent && !isFinalStatusUpdate) {
                        // Text content from current event
                        if (
                            lastMsg &&
                            !lastMsg.isUser &&
                            !lastMsg.isComplete &&
                            lastMsg.metadata?.messageId === currentMessageId &&
                            lastMsg.text !== undefined &&
                            !lastMsg.toolEvents &&
                            !lastMsg.files &&
                            !lastMsg.artifactNotification &&
                            (lastMsg.metadata?.lastProcessedEventSequence || 0) < currentEventSequence
                        ) {
                            // Append text to lastMsg
                            newMessages[newMessages.length - 1] = { ...lastMsg, text: (lastMsg.text || "") + messageContent, metadata: { ...lastMsg.metadata, sessionId, lastProcessedEventSequence: currentEventSequence } };
                            appendedToExistingBubble = true;
                        } else {
                            // Create new bubble for text
                            addNewMainBubble({ text: messageContent }, currentEventSequence);
                        }
                    }
                    // These always create new bubbles if content is present and not a final response event (errorContent handles its own finality)
                    if (currentToolEvents.length > 0 && !isFinalResponseEvent) {
                        addNewMainBubble({ toolEvents: currentToolEvents }, currentEventSequence);
                    }
                    if (receivedFiles.length > 0 && !isFinalResponseEvent) {
                        addNewMainBubble({ files: receivedFiles }, currentEventSequence);
                        artifactsRefetchIfNeeded(receivedFiles);
                    }
                    if (artifactNotificationData && !isFinalResponseEvent) {
                        addNewMainBubble({ artifactNotification: artifactNotificationData }, currentEventSequence);
                    }
                    if (errorContent) {
                        console.log("DEBUG: Creating error bubble", { messageContent, errorContent, currentEventSequence });
                        addNewMainBubble({ text: messageContent, isComplete: true, isError: true }, currentEventSequence); // Error content also sets the flag and isComplete
                    }
                }

                // Mark previous messages as complete
                if (isEndOfThisTurn) {
                    // Mark all relevant non-user, non-status messages of this turn as complete
                    for (let i = 0; i < newMessages.length; i++) {
                        if (newMessages[i] && !newMessages[i].isUser && newMessages[i].metadata?.messageId === currentMessageId && !newMessages[i].isStatusBubble) {
                            // Ensure we don't try to re-complete an already completed message unless it's the error itself
                            if (!newMessages[i].isComplete || (errorContent && newMessages[i].text === messageContent)) {
                                newMessages[i] = { ...newMessages[i], isComplete: true, metadata: { ...newMessages[i].metadata, lastProcessedEventSequence: currentEventSequence } };
                            }
                        }
                    }
                } else if (newMainBubbleAddedByThisEvent && !appendedToExistingBubble) {
                    // A new main content bubble was added (not appended). Mark the previous agent bubble of this turn (if any) as complete.
                    if (lastMsgOriginalIndex >= 0 && lastMsgOriginalIndex < newMessages.length) {
                        const messageToMarkComplete = newMessages[lastMsgOriginalIndex]; // This was the message at the end before new bubbles were added
                        if (messageToMarkComplete && !messageToMarkComplete.isUser && messageToMarkComplete.metadata?.messageId === currentMessageId && !messageToMarkComplete.isStatusBubble && !messageToMarkComplete.isComplete) {
                            newMessages[lastMsgOriginalIndex] = {
                                ...messageToMarkComplete,
                                isComplete: true,
                                metadata: { ...messageToMarkComplete.metadata, lastProcessedEventSequence: currentEventSequence },
                            };
                        }
                    }
                }

                const isTaskEnding = isFinalResponseEvent || isErrorResponse || (isFinalStatusUpdate && isCancelling);
                if (!isTaskEnding) {
                    // The status bubble logic
                    const statusTextForBubble = agentStatusText ?? latestStatusText.current;
                    if (statusTextForBubble) {
                        newMessages.push({
                            taskId: currentTaskId ?? undefined,
                            text: statusTextForBubble,
                            isUser: false,
                            isStatusBubble: true,
                            isComplete: false,
                            metadata: { sessionId, messageId: currentMessageId, lastProcessedEventSequence: currentEventSequence },
                        });
                    }
                } else {
                    latestStatusText.current = null;
                }
                return newMessages;
            });

            // If task is cancelled or failed while in cancelling state
            if (isCancelling && (isFinalStatusUpdate || isErrorResponse)) {
                addNotification(isErrorResponse ? "Task failed during cancellation." : "Task successfully cancelled.");
                if (cancelTimeoutRef.current) {
                    clearTimeout(cancelTimeoutRef.current);
                    cancelTimeoutRef.current = null;
                }
                setIsCancelling(false);

                // Remove status bubble messages when cancellation is successful
                setMessages(prev => prev.filter(msg => !msg.isStatusBubble));
            }

            const isTaskReallyEnding = isFinalResponseEvent || isErrorResponse || (isFinalStatusUpdate && isCancelling);

            if (isTaskReallyEnding) {
                setIsResponding(false);
                if (currentEventSource.current) {
                    currentEventSource.current.close();
                    currentEventSource.current = null;
                }
                setCurrentTaskId(null);
                isFinalizing.current = true;
                artifactsRefetch(); 
                setTimeout(() => {
                    isFinalizing.current = false;
                }, 100);
            }
        },
        [currentTaskId, isCancelling, addNotification, sessionId, artifactsRefetchIfNeeded, artifactsRefetch]
    );

    const closeCurrentEventSource = useCallback(() => {
        if (cancelTimeoutRef.current) {
            clearTimeout(cancelTimeoutRef.current);
            cancelTimeoutRef.current = null;
        }
        setIsCancelling(false);

        if (currentEventSource.current) {
            currentEventSource.current.removeEventListener("status_update", handleSseMessage);
            currentEventSource.current.removeEventListener("artifact_update", handleSseMessage);
            currentEventSource.current.removeEventListener("final_response", handleSseMessage);
            currentEventSource.current.removeEventListener("error", handleSseMessage);
            currentEventSource.current.close();
            currentEventSource.current = null;
        }
        isFinalizing.current = false;
    }, [handleSseMessage]);

    const handleNewSession = useCallback(async () => {
        const log_prefix = "ChatProvider.handleNewSession:";
        console.log(`${log_prefix} Starting new session process...`);

        // 1. Close current connections and cancel tasks
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

        // 2. Clear cancel timeout
        if (cancelTimeoutRef.current) {
            clearTimeout(cancelTimeoutRef.current);
            cancelTimeoutRef.current = null;
        }
        setIsCancelling(false);

        try {
            // 3. Call backend to create new A2A session
            console.log(`${log_prefix} Requesting new session from backend...`);
            const response = await authenticatedFetch(`${apiPrefix}/sessions/new`, {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: `HTTP error ${response.status}`,
                }));
                throw new Error(errorData.detail || `Failed to create new session: ${response.status}`);
            }

            const result = await response.json();
            const backendSessionId = result?.result?.sessionId;

            if (!backendSessionId) {
                throw new Error("Backend did not return a valid session ID");
            }

            console.log(`${log_prefix} Received new backend session ID: ${backendSessionId}`);

            // 4. Update frontend state with backend session ID
            setSessionId(backendSessionId);

            // 5. Reset UI state with new session ID
            const welcomeMessages = configWelcomeMessage
                ? [
                      {
                          text: configWelcomeMessage,
                          isUser: false,
                          isComplete: true,
                          metadata: {
                              sessionId: backendSessionId,
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

            // 6. Refresh artifacts (should now be empty for new session)
            console.log(`${log_prefix} Refreshing artifacts for new session...`);
            await artifactsRefetch();

            // 7. Success notification
            addNotification("New session started successfully.");
            console.log(`${log_prefix} New session setup complete.`);
        } catch (error) {
            console.error(`${log_prefix} Error creating new session:`, error);
            addNotification(`Failed to create new session: ${error instanceof Error ? error.message : "Unknown error"}`);

            // 8. Fallback to frontend-only reset if backend call fails
            console.log(`${log_prefix} Falling back to frontend-only session reset...`);
            const fallbackSessionId = `web-session-${Date.now()}`;
            setSessionId(fallbackSessionId);

            const fallbackMessages = configWelcomeMessage
                ? [
                      {
                          text: configWelcomeMessage,
                          isUser: false,
                          isComplete: true,
                          metadata: {
                              sessionId: fallbackSessionId,
                              lastProcessedEventSequence: 0,
                          },
                      },
                  ]
                : [];

            setMessages(fallbackMessages);
            setUserInput("");
            setIsResponding(false);
            setCurrentTaskId(null);
            setTaskIdInSidePanel(null);
            isFinalizing.current = false;
            latestStatusText.current = null;
            sseEventSequenceRef.current = 0;

            addNotification("Session reset to frontend-only mode due to backend error.");
        }

        // 9. Dispatch custom event for other components
        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("new-chat-session", {
                    detail: { sessionId: sessionId },
                })
            );
        }
    }, [closeCurrentEventSource, isResponding, currentTaskId, selectedAgentName, isCancelling, apiPrefix, configWelcomeMessage, addNotification, artifactsRefetch, sessionId]);

    const handleCancel = useCallback(async () => {
        if ((!isResponding && !isCancelling) || !currentTaskId || !selectedAgentName) {
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
            const response = await authenticatedFetch(`${apiPrefix}/tasks/cancel`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ agent_name: selectedAgentName, task_id: currentTaskId }),
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
    }, [isResponding, isCancelling, currentTaskId, selectedAgentName, apiPrefix, addNotification, closeCurrentEventSource]);

    const handleSseOpen = useCallback(() => {
        /* console.log for SSE open */
    }, []);
    const handleSseError = useCallback(() => {
        if (isResponding && !isFinalizing.current && !isCancelling) {
            addNotification("Connection error with agent updates.");
        }
        if (!isFinalizing.current) {
            setIsResponding(false);
            if (!isCancelling) {
                closeCurrentEventSource();
                setCurrentTaskId(null);
            }
            latestStatusText.current = null;
        }
        setMessages(prev => prev.filter(msg => !msg.isStatusBubble).map((m, i, arr) => (i === arr.length - 1 && !m.isUser ? { ...m, isComplete: true } : m)));
    }, [addNotification, closeCurrentEventSource, isResponding, isCancelling]);

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
            const userMsg: MessageFE = { text: currentInput, isUser: true, uploadedFiles: currentFiles.length > 0 ? currentFiles : undefined, metadata: { sessionId, lastProcessedEventSequence: 0 } };
            const initialStatusText = "Thinking";
            latestStatusText.current = initialStatusText;
            const statusMsg: MessageFE = { text: initialStatusText, isUser: false, isStatusBubble: true, isComplete: false, metadata: { sessionId, lastProcessedEventSequence: 0 } };
            setMessages(prev => [...prev, userMsg, statusMsg]);
            setUserInput("");
            try {
                const formData = new FormData();
                formData.append("agent_name", selectedAgentName);
                formData.append("message", currentInput);
                currentFiles.forEach(file => formData.append("files", file, file.name));

                console.log("ChatProvider handleSubmit: Sending POST to /tasks/subscribe");
                const response = await authenticatedFetch(`${apiPrefix}/tasks/subscribe`, { method: "POST", body: formData });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
                    console.error("ChatProvider handleSubmit: Error from /tasks/subscribe", response.status, errorData);
                    throw new Error(errorData.detail || `HTTP error ${response.status}`);
                }
                const result = await response.json();
                const taskId = result?.result?.taskId;

                if (!taskId) {
                    console.error("ChatProvider handleSubmit: Backend did not return a valid taskId. Result:", result);
                    throw new Error("Backend did not return a valid taskId.");
                }

                console.log(`ChatProvider handleSubmit: Received taskId ${taskId}. Setting currentTaskId and taskIdInSidePanel.`);
                setCurrentTaskId(taskId);
                // Auto-display the new task in the side panel
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
        [userInput, isResponding, isCancelling, sessionId, selectedAgentName, apiPrefix, addNotification, closeCurrentEventSource]
    );

    useEffect(() => {
        if (artifactsError) {
            addNotification(`Error fetching files: ${artifactsError}`, "error");
        }
    }, [addNotification, artifactsError]);

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
                closeCurrentEventSource();
            };
        } else {
            console.log(`ChatProvider Effect: currentTaskId is null or apiPrefix missing. Ensuring EventSource is closed.`);
            closeCurrentEventSource();
        }
    }, [currentTaskId, apiPrefix]);

    const contextValue: ChatContextValue = {
        sessionId,
        messages,
        setMessages,
        userInput,
        setUserInput,
        isResponding,
        currentTaskId,
        isCancelling,
        handleNewSession,
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
    };

    return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};