/**
 * Shared hook for SharedChatViewPage and SharedSessionPage.
 *
 * Encapsulates all data-fetching, state management, message parsing, and
 * artifact conversion logic that both shared-session views need.
 */

import { useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useSharedSessionView, useForkSharedChat } from "@/lib/api/share";
import { downloadSharedArtifact } from "@/lib/api/share";
import type { SharedArtifact } from "@/lib/types/share";
import type { MessageBubble } from "@/lib/types/storage";
import type { MessageFE, ArtifactInfo, ArtifactPart, PartFE } from "@/lib/types";
import { downloadBlob } from "@/lib/utils/download";
import { formatTimestamp } from "@/lib/utils/format";
import { extractRagDataFromTasks } from "@/lib/utils/taskUtils";

/** Format epoch ms as YYYY/MM/DD */
export function formatDateYMD(epochMs: number): string {
    return formatTimestamp(new Date(epochMs).toISOString(), "date");
}

/** Convert a SharedArtifact to ArtifactInfo for unified component use. */
function convertToArtifactInfo(artifact: SharedArtifact): ArtifactInfo {
    return {
        filename: artifact.filename,
        mime_type: artifact.mimeType,
        size: artifact.size,
        last_modified: artifact.lastModified || new Date().toISOString(),
        version: artifact.version ?? undefined,
        versionCount: artifact.versionCount ?? undefined,
        description: artifact.description,
        source: artifact.source ?? undefined,
    };
}

export function useSharedSession() {
    const { shareId } = useParams<{ shareId: string }>();
    const navigate = useNavigate();

    // React Query for data fetching
    const sessionQuery = useSharedSessionView(shareId || "");
    const forkMutation = useForkSharedChat();

    const session = sessionQuery.data ?? null;
    const loading = sessionQuery.isLoading;
    const error = sessionQuery.error ? (sessionQuery.error instanceof Error ? sessionQuery.error.message : "Failed to load shared session") : null;
    const isForking = forkMutation.isPending;

    // UI-only local state
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(true);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "workflow" | "sources">("files");
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

    // Custom download handler for shared artifacts using the share API
    const handleSharedArtifactDownload = useCallback(
        async (artifact: ArtifactInfo) => {
            if (!shareId) return;
            try {
                const blob = await downloadSharedArtifact(shareId, artifact.filename);
                downloadBlob(blob, artifact.filename);
            } catch (err) {
                console.error("Failed to download artifact:", err);
            }
        },
        [shareId]
    );

    // Fork shared chat into user's own sessions
    const handleForkChat = useCallback(async () => {
        if (!shareId || isForking) return;

        try {
            const result = await forkMutation.mutateAsync(shareId);
            const newSessionId = result?.sessionId;
            navigate("/chat");
            setTimeout(() => {
                window.dispatchEvent(new CustomEvent("new-chat-session"));
                if (newSessionId) {
                    window.dispatchEvent(new CustomEvent("switch-to-session", { detail: { sessionId: newSessionId } }));
                }
            }, 200);
        } catch (err) {
            console.error("Failed to fork chat:", err);
        }
    }, [shareId, isForking, navigate, forkMutation]);

    // Extract RAG data from all tasks
    const ragData = useMemo(() => {
        if (!session) return [];
        return extractRagDataFromTasks(session.tasks);
    }, [session]);

    // Convert SharedArtifact[] to ArtifactInfo[]
    const convertedArtifacts = useMemo(() => {
        if (!session?.artifacts) return [];
        return session.artifacts.map(convertToArtifactInfo);
    }, [session?.artifacts]);

    // Parse message bubbles from tasks into MessageFE format for ChatMessage rendering
    const messages: MessageFE[] = useMemo(() => {
        if (!session) return [];
        const result: MessageFE[] = [];

        for (const task of session.tasks) {
            try {
                const taskId = task.workflowTaskId || task.id;
                const bubbles = typeof task.messageBubbles === "string" ? JSON.parse(task.messageBubbles) : task.messageBubbles;

                if (!Array.isArray(bubbles)) continue;

                (bubbles as MessageBubble[]).forEach((bubble: MessageBubble) => {
                    const parts: PartFE[] = [];
                    const isUser = bubble.type === "user";

                    // Convert uploadedFiles to File-like objects
                    const uploadedFiles: File[] = [];
                    if (bubble.uploadedFiles && Array.isArray(bubble.uploadedFiles)) {
                        for (const f of bubble.uploadedFiles) {
                            const fileObj = f as { name?: string; filename?: string; mimeType?: string; mime_type?: string; type?: string };
                            const fileName = fileObj.name || fileObj.filename || "Attached file";
                            const fileType = fileObj.mimeType || fileObj.mime_type || fileObj.type || "";
                            uploadedFiles.push(new File([], fileName, { type: fileType }));
                        }
                    }

                    // Process parts array
                    if (bubble.parts && Array.isArray(bubble.parts)) {
                        for (const part of bubble.parts) {
                            const partObj = part as {
                                kind?: string;
                                text?: string;
                                file?: { name?: string; filename?: string; mimeType?: string; mime_type?: string };
                                artifact?: { name?: string; filename?: string; status?: string };
                            };
                            if (partObj.kind === "text" && partObj.text) {
                                parts.push({ kind: "text", text: partObj.text });
                            } else if (partObj.kind === "file" && partObj.file) {
                                parts.push({
                                    kind: "file",
                                    file: {
                                        name: partObj.file.name || partObj.file.filename || "Attached file",
                                        mimeType: partObj.file.mimeType || partObj.file.mime_type,
                                        uri: "",
                                    },
                                });
                            } else if (partObj.kind === "artifact") {
                                const artifactData = partObj.artifact || partObj;
                                const artifactName = (artifactData as { name?: string; filename?: string }).name || (artifactData as { name?: string; filename?: string }).filename || "Artifact";
                                const fullArtifact = convertedArtifacts.find(a => a.filename === artifactName);
                                parts.push({
                                    kind: "artifact",
                                    status: ((artifactData as { status?: string }).status as ArtifactPart["status"]) || "completed",
                                    name: artifactName,
                                    file: fullArtifact
                                        ? {
                                              name: fullArtifact.filename,
                                              mime_type: fullArtifact.mime_type,
                                          }
                                        : { name: artifactName },
                                } as ArtifactPart);
                            }
                        }
                    } else if (bubble.text) {
                        parts.push({ kind: "text", text: bubble.text });
                    }

                    result.push({
                        taskId,
                        createdTime: task.createdTime,
                        role: isUser ? "user" : "agent",
                        isUser,
                        isComplete: true,
                        isError: bubble.isError || false,
                        displayHtml: bubble.displayHtml,
                        contextQuote: bubble.contextQuote,
                        contextQuoteSourceId: bubble.contextQuoteSourceId,
                        senderDisplayName: bubble.senderDisplayName,
                        senderEmail: bubble.senderEmail,
                        uploadedFiles: uploadedFiles.length > 0 ? uploadedFiles : undefined,
                        parts,
                        metadata: {
                            messageId: bubble.id,
                            sessionId: task.sessionId,
                        },
                    });
                });
            } catch (e) {
                console.error("Failed to parse message bubbles:", e);
            }
        }
        return result;
    }, [session, convertedArtifacts]);

    // Compute which message is last per task (for workflow button display)
    const lastMessageIndexByTaskId = useMemo(() => {
        const map = new Map<string, number>();
        messages.forEach((message, index) => {
            if (message.taskId) {
                map.set(message.taskId, index);
            }
        });
        return map;
    }, [messages]);

    const hasRagSources = ragData.length > 0;

    const toggleSidePanel = useCallback(() => {
        setIsSidePanelCollapsed(prev => !prev);
    }, []);

    const openSidePanelTab = useCallback((tab: "files" | "workflow" | "sources") => {
        setIsSidePanelCollapsed(false);
        setActiveSidePanelTab(tab);
    }, []);

    // Session ID for the SharedChatProvider
    const sessionIdForProvider = session?.tasks[0]?.sessionId || session?.shareId || "";

    // Callback for SharedChatProvider's onOpenSidePanelTab
    const handleProviderTabOpen = useCallback(
        (tab: string) => {
            if (tab === "activity") {
                openSidePanelTab("workflow");
            } else if (tab === "rag") {
                openSidePanelTab("sources");
            } else if (tab === "files") {
                openSidePanelTab("files");
            }
        },
        [openSidePanelTab]
    );

    return {
        shareId,
        navigate,
        session,
        loading,
        error,
        isForking,

        // Side panel state
        isSidePanelCollapsed,
        activeSidePanelTab,
        setActiveSidePanelTab,
        selectedTaskId,
        setSelectedTaskId,
        toggleSidePanel,
        openSidePanelTab,

        // Derived data
        convertedArtifacts,
        ragData,
        hasRagSources,
        messages,
        lastMessageIndexByTaskId,
        sessionIdForProvider,

        // Actions
        handleSharedArtifactDownload,
        handleForkChat,
        handleProviderTabOpen,
    };
}
