/**
 * SharedChatViewPage - In-app view of a shared chat session (inside AppLayout)
 *
 * Unlike SharedSessionPage (standalone, outside AppLayout), this component renders
 * inside the main app layout with sidebar and navigation visible. It provides a
 * read-only view of a shared chat with the option to fork or navigate to the
 * original chat (if owner).
 *
 * Uses the full ChatMessage component for pixel-perfect rendering parity with ChatPage.
 */

import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertCircle, FileText, Network, PanelRightIcon, Link2, GitFork, Loader2, MessageSquare, UserLock, Info } from "lucide-react";
import { Button, Spinner, Tabs, TabsList, TabsTrigger, TabsContent, ResizablePanelGroup, ResizablePanel, ResizableHandle, Tooltip, TooltipContent, TooltipTrigger, CHAT_STYLES } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { viewSharedSession, downloadSharedArtifact, forkSharedChat } from "@/lib/api/shareApi";
import type { SharedSessionView, SharedArtifact } from "@/lib/types/share";
import type { MessageBubble } from "@/lib/types/storage";
import type { MessageFE, RAGSearchResult, ArtifactInfo, ArtifactPart, PartFE } from "@/lib/types";
import { ArtifactPanel } from "@/lib/components/chat/artifact/ArtifactPanel";
import { SharedWorkflowPanel } from "@/lib/components/share/SharedWorkflowPanel";
import { ChatMessage } from "@/lib/components/chat";
import { RAGInfoPanel } from "@/lib/components/chat/rag/RAGInfoPanel";
import { SharedChatProvider } from "@/lib/providers/SharedChatProvider";
import { downloadBlob } from "@/lib/utils/download";

/**
 * Convert SharedArtifact to ArtifactInfo for use with unified components
 */
function convertToArtifactInfo(artifact: SharedArtifact): ArtifactInfo {
    return {
        filename: artifact.filename,
        mime_type: artifact.mime_type,
        size: artifact.size,
        last_modified: artifact.last_modified || new Date().toISOString(),
        version: artifact.version ?? undefined,
        versionCount: artifact.version_count ?? undefined,
        description: artifact.description,
        source: artifact.source ?? undefined,
    };
}

export function SharedChatViewPage() {
    const { shareId } = useParams<{ shareId: string }>();
    const navigate = useNavigate();
    const [session, setSession] = useState<SharedSessionView | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(true);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "workflow" | "sources">("files");
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [isForking, setIsForking] = useState(false);

    // Load shared session data
    const loadSharedSession = useCallback(async (id: string) => {
        setLoading(true);
        setError(null);
        try {
            const data = await viewSharedSession(id);
            setSession(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load shared session");
        } finally {
            setLoading(false);
        }
    }, []);

    // Custom download handler for shared artifacts using the share API
    const handleSharedArtifactDownload = useCallback(
        async (artifact: ArtifactInfo) => {
            if (!shareId) return;

            try {
                const blob = await downloadSharedArtifact(shareId, artifact.filename);
                downloadBlob(blob, artifact.filename);
            } catch (error) {
                console.error("Failed to download artifact:", error);
            }
        },
        [shareId]
    );

    // Fork shared chat into user's own sessions
    const handleForkChat = useCallback(async () => {
        if (!shareId || isForking) return;

        setIsForking(true);
        try {
            const result = await forkSharedChat(shareId);
            const newSessionId = result?.session_id;
            // Navigate to chat and switch to the forked session
            navigate("/chat");
            setTimeout(() => {
                window.dispatchEvent(new CustomEvent("new-chat-session"));
                if (newSessionId) {
                    window.dispatchEvent(new CustomEvent("switch-to-session", { detail: { sessionId: newSessionId } }));
                }
            }, 200);
        } catch (err) {
            console.error("Failed to fork chat:", err);
        } finally {
            setIsForking(false);
        }
    }, [shareId, isForking, navigate]);

    useEffect(() => {
        if (shareId) {
            loadSharedSession(shareId);
        }
    }, [shareId, loadSharedSession]);

    // Extract RAG data from all tasks
    const ragData = useMemo(() => {
        if (!session) return [];

        const allRagData: RAGSearchResult[] = [];

        for (const task of session.tasks) {
            const taskId = task.workflow_task_id || task.id;

            let taskMetadata = task.task_metadata;
            if (typeof taskMetadata === "string") {
                try {
                    taskMetadata = JSON.parse(taskMetadata);
                } catch {
                    taskMetadata = null;
                }
            }

            if (taskMetadata && Array.isArray(taskMetadata.rag_data)) {
                for (const ragEntry of taskMetadata.rag_data) {
                    allRagData.push({
                        ...ragEntry,
                        taskId: taskId,
                    });
                }
            }
        }

        return allRagData;
    }, [session]);

    // Convert SharedArtifact[] to ArtifactInfo[] for the unified ArtifactPanel
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
                const taskId = task.workflow_task_id || task.id;
                const bubbles = typeof task.message_bubbles === "string" ? JSON.parse(task.message_bubbles) : task.message_bubbles;

                if (!Array.isArray(bubbles)) continue;

                (bubbles as MessageBubble[]).forEach((bubble: MessageBubble) => {
                    const parts: PartFE[] = [];
                    const isUser = bubble.type === "user";

                    // Convert uploadedFiles to File-like objects for the uploadedFiles field
                    // (ChatMessage renders these as file upload badges via getUploadedFiles)
                    const uploadedFiles: File[] = [];
                    if (bubble.uploadedFiles && Array.isArray(bubble.uploadedFiles)) {
                        for (const f of bubble.uploadedFiles) {
                            const fileObj = f as { name?: string; filename?: string; mimeType?: string; mime_type?: string; type?: string };
                            const fileName = fileObj.name || fileObj.filename || "Attached file";
                            const fileType = fileObj.mimeType || fileObj.mime_type || fileObj.type || "";
                            // Create a minimal File-like object with name and type properties
                            uploadedFiles.push(new File([], fileName, { type: fileType }));
                        }
                    }

                    // Process parts array - keep text as-is (let ChatMessage handle embed signals)
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
                                        uri: "", // Required by A2A FilePart type
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
                        createdTime: task.created_time,
                        role: isUser ? "user" : "agent",
                        isUser,
                        isComplete: true, // All shared messages are historical/complete
                        isError: bubble.isError || false,
                        displayHtml: bubble.displayHtml,
                        contextQuote: bubble.contextQuote,
                        contextQuoteSourceId: bubble.contextQuoteSourceId,
                        senderDisplayName: bubble.sender_display_name,
                        senderEmail: bubble.sender_email,
                        uploadedFiles: uploadedFiles.length > 0 ? uploadedFiles : undefined,
                        parts,
                        metadata: {
                            messageId: bubble.id,
                            sessionId: task.session_id,
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

    // Check if there are any RAG sources to show
    const hasRagSources = ragData.length > 0;

    const toggleSidePanel = () => {
        setIsSidePanelCollapsed(!isSidePanelCollapsed);
    };

    // Render side panel content
    const renderSidePanel = () => {
        if (isSidePanelCollapsed) {
            return (
                <div className="bg-background flex h-full w-full flex-col items-center border-l py-4">
                    <Button variant="ghost" size="sm" onClick={toggleSidePanel} className="h-10 w-10 p-0" tooltip="Expand Panel">
                        <PanelRightIcon className="size-5" />
                    </Button>

                    <div className="bg-border my-4 h-px w-8"></div>

                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                            setIsSidePanelCollapsed(false);
                            setActiveSidePanelTab("files");
                        }}
                        className="mb-2 h-10 w-10 p-0"
                        tooltip="Files"
                    >
                        <FileText className="size-5" />
                    </Button>

                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                            setIsSidePanelCollapsed(false);
                            setActiveSidePanelTab("workflow");
                        }}
                        className="mb-2 h-10 w-10 p-0"
                        tooltip="Workflow"
                    >
                        <Network className="size-5" />
                    </Button>

                    {hasRagSources && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setIsSidePanelCollapsed(false);
                                setActiveSidePanelTab("sources");
                            }}
                            className="h-10 w-10 p-0"
                            tooltip="Sources"
                        >
                            <Link2 className="size-5" />
                        </Button>
                    )}
                </div>
            );
        }

        return (
            <div className="bg-background flex h-full flex-col border-l">
                <div className="m-1 min-h-0 flex-1">
                    <Tabs value={activeSidePanelTab} onValueChange={value => setActiveSidePanelTab(value as "files" | "workflow" | "sources")} className="flex h-full flex-col">
                        <div className="@container flex gap-2 p-2">
                            <Button variant="ghost" onClick={toggleSidePanel} className="shrink-0 p-1" tooltip="Collapse Panel">
                                <PanelRightIcon className="size-5" />
                            </Button>
                            <TabsList className="flex min-w-0 flex-1 bg-transparent p-0">
                                <TabsTrigger
                                    value="files"
                                    title="Files"
                                    className="border-border bg-muted data-[state=active]:bg-background relative min-w-0 flex-1 cursor-pointer rounded-none rounded-l-md border border-r-0 px-2 data-[state=active]:z-10"
                                >
                                    <FileText className="h-4 w-4 shrink-0" />
                                    <span className="ml-1.5 hidden truncate @[240px]:inline">Files</span>
                                </TabsTrigger>
                                <TabsTrigger
                                    value="workflow"
                                    title="Workflow"
                                    className={`border-border bg-muted data-[state=active]:bg-background relative min-w-0 flex-1 cursor-pointer rounded-none border px-2 data-[state=active]:z-10 ${hasRagSources ? "border-r-0" : "rounded-r-md"}`}
                                >
                                    <Network className="h-4 w-4 shrink-0" />
                                    <span className="ml-1.5 hidden truncate @[240px]:inline">Workflow</span>
                                </TabsTrigger>
                                {hasRagSources && (
                                    <TabsTrigger
                                        value="sources"
                                        title="Sources"
                                        className="border-border bg-muted data-[state=active]:bg-background relative min-w-0 flex-1 cursor-pointer rounded-none rounded-r-md border px-2 data-[state=active]:z-10"
                                    >
                                        <Link2 className="h-4 w-4 shrink-0" />
                                        <span className="ml-1.5 hidden truncate @[240px]:inline">Sources</span>
                                    </TabsTrigger>
                                )}
                            </TabsList>
                        </div>
                        <div className="min-h-0 flex-1">
                            <TabsContent value="files" className="m-0 h-full">
                                <div className="h-full">
                                    <ArtifactPanel readOnly={true} onDownloadOverride={handleSharedArtifactDownload} />
                                </div>
                            </TabsContent>
                            <TabsContent value="workflow" className="m-0 h-full">
                                <div className="h-full">
                                    <SharedWorkflowPanel taskEvents={session?.task_events} selectedTaskId={selectedTaskId} onTaskSelect={setSelectedTaskId} />
                                </div>
                            </TabsContent>
                            {hasRagSources && (
                                <TabsContent value="sources" className="m-0 h-full">
                                    <div className="h-full">
                                        <RAGInfoPanel ragData={ragData} enabled={true} />
                                    </div>
                                </TabsContent>
                            )}
                        </div>
                    </Tabs>
                </div>
            </div>
        );
    };

    // Loading state
    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Spinner size="large" variant="primary">
                    <p className="text-muted-foreground mt-4 text-sm">Loading shared chat...</p>
                </Spinner>
            </div>
        );
    }

    // Error state
    if (error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-destructive h-16 w-16" />
                <h1 className="text-2xl font-semibold">Unable to View Shared Chat</h1>
                <p className="text-muted-foreground max-w-md text-center">{error}</p>
                <Button variant="outline" onClick={() => navigate("/chat")}>
                    Go to Chat
                </Button>
            </div>
        );
    }

    // Not found state
    if (!session) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-muted-foreground h-16 w-16" />
                <h1 className="text-2xl font-semibold">Shared Chat Not Found</h1>
                <p className="text-muted-foreground">This shared chat may have been deleted or the link is invalid.</p>
                <Button variant="outline" onClick={() => navigate("/chat")}>
                    Go to Chat
                </Button>
            </div>
        );
    }

    // Get session ID for the provider
    const sessionIdForProvider = session.tasks[0]?.session_id || session.share_id;

    // Header buttons
    const headerButtons = [
        <div key="shared-info" className="flex items-center gap-2 text-sm text-(--color-secondary-text-wMain)">
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className="inline-flex cursor-pointer">
                        <UserLock className="h-4 w-4 text-(--color-secondary-wMain)" />
                    </span>
                </TooltipTrigger>
                <TooltipContent>
                    Shared by <span className="font-bold">{session.tasks[0]?.user_id || "Unknown"}</span> on{" "}
                    <span className="font-bold">
                        {(() => {
                            const d = new Date(session.created_time);
                            return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
                        })()}
                    </span>
                </TooltipContent>
            </Tooltip>
            <span className="text-muted-foreground text-xs">Viewer</span>
            {session.snapshot_time && (
                <>
                    <div className="bg-border h-4 w-px" />
                    <span className="text-muted-foreground text-xs">
                        Snapshot from{" "}
                        {(() => {
                            const d = new Date(session.snapshot_time);
                            return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
                        })()}
                    </span>
                </>
            )}
        </div>,
        session?.is_owner && session?.session_id ? (
            <Button key="go-to-chat" variant="outline" size="sm" onClick={() => navigate(`/chat?sessionId=${session.session_id}`)}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Go to Chat
            </Button>
        ) : (
            <Button key="save-as-my-chat" variant="outline" size="sm" onClick={handleForkChat} disabled={isForking}>
                {isForking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitFork className="mr-2 h-4 w-4" />}
                Save as My Chat
            </Button>
        ),
    ].filter(Boolean) as React.ReactNode[];

    return (
        <SharedChatProvider
            artifacts={convertedArtifacts}
            ragData={ragData}
            sessionId={sessionIdForProvider}
            shareId={shareId || ""}
            onOpenSidePanelTab={tab => {
                // Map ChatMessage's tab names to shared page's tab names
                if (tab === "activity") {
                    setActiveSidePanelTab("workflow");
                    setIsSidePanelCollapsed(false);
                } else if (tab === "rag") {
                    setActiveSidePanelTab("sources");
                    setIsSidePanelCollapsed(false);
                } else if (tab === "files") {
                    setActiveSidePanelTab("files");
                    setIsSidePanelCollapsed(false);
                }
            }}
            onSetTaskIdInSidePanel={setSelectedTaskId}
        >
            <div className="relative flex h-screen w-full flex-col overflow-hidden">
                <Header title={session.title} buttons={headerButtons} />

                <div className="flex min-h-0 flex-1">
                    <div className="min-h-0 flex-1 overflow-x-auto">
                        <ResizablePanelGroup direction="horizontal" autoSaveId="shared-chat-view-side-panel" className="h-full">
                            {/* Messages panel */}
                            <ResizablePanel defaultSize={isSidePanelCollapsed ? 96 : 70} minSize={50} id="shared-chat-view-messages-panel">
                                <div className="flex h-full w-full flex-col">
                                    <div className="flex min-h-0 flex-1 flex-col py-6">
                                        <main className="h-full overflow-y-auto px-6">
                                            <div className="mx-auto max-w-3xl space-y-4">
                                                {messages.length === 0 ? (
                                                    <div className="text-muted-foreground py-12 text-center">
                                                        <p>No messages in this shared chat.</p>
                                                    </div>
                                                ) : (
                                                    messages.map((message, index) => {
                                                        const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                                                        return (
                                                            <div key={message.metadata?.messageId || `msg-${index}`}>
                                                                <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} />
                                                            </div>
                                                        );
                                                    })
                                                )}
                                            </div>
                                        </main>

                                        {/* Read-only banner instead of ChatInputArea */}
                                        <div style={CHAT_STYLES}>
                                            <div className="bg-muted/50 border-border mx-auto flex max-w-3xl items-center gap-3 rounded-lg border px-4 py-3">
                                                <Info className="text-muted-foreground h-5 w-5 flex-shrink-0" />
                                                <span className="text-muted-foreground text-sm">This is a shared chat. Fork it to continue the conversation.</span>
                                                {!(session?.is_owner && session?.session_id) && (
                                                    <Button variant="outline" size="sm" onClick={handleForkChat} disabled={isForking} className="ml-auto flex-shrink-0">
                                                        {isForking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitFork className="mr-2 h-4 w-4" />}
                                                        Save as My Chat
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </ResizablePanel>

                            <ResizableHandle />

                            {/* Side panel - always visible */}
                            <ResizablePanel defaultSize={isSidePanelCollapsed ? 4 : 30} minSize={isSidePanelCollapsed ? 4 : 20} maxSize={isSidePanelCollapsed ? 4 : 50} id="shared-chat-view-side-panel">
                                {renderSidePanel()}
                            </ResizablePanel>
                        </ResizablePanelGroup>
                    </div>
                </div>
            </div>
        </SharedChatProvider>
    );
}
