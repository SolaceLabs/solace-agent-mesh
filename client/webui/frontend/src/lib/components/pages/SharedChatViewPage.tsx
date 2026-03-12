/**
 * SharedChatViewPage - In-app view of a shared chat session (inside AppLayout)
 *
 * Unlike SharedSessionPage (standalone, outside AppLayout), this component renders
 * inside the main app layout with sidebar and navigation visible. It provides a
 * read-only view of a shared chat with the option to fork or navigate to the
 * original chat (if owner).
 */

import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AlertCircle, FileText, Network, PanelRightIcon, Link2, GitFork, Loader2, MessageSquare, UserLock, Info } from "lucide-react";
import { Button, Spinner, Tabs, TabsList, TabsTrigger, TabsContent, ResizablePanelGroup, ResizablePanel, ResizableHandle, ChatBubble, ChatBubbleMessage, Tooltip, TooltipContent, TooltipTrigger, CHAT_STYLES } from "@/lib/components/ui";
import { MessageAttribution } from "@/lib/components/chat/MessageAttribution";
import { CHAT_BUBBLE_MESSAGE_STYLES } from "@/lib/components/ui/chat/chat-bubble-styles";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { Header } from "@/lib/components/header";
import { viewSharedSession, downloadSharedArtifact, forkSharedChat } from "@/lib/api/shareApi";
import type { SharedSessionView, SharedArtifact } from "@/lib/types/share";
import type { MessageBubble } from "@/lib/types/storage";
import type { RAGSearchResult, ArtifactInfo } from "@/lib/types";
import { ArtifactPanel } from "@/lib/components/chat/artifact/ArtifactPanel";
import { SharedWorkflowPanel } from "@/lib/components/share/SharedWorkflowPanel";
import { FileMessage, ArtifactMessage } from "@/lib/components/chat/file";
import { TextWithCitations } from "@/lib/components/chat/Citation";
import { parseCitations } from "@/lib/utils/citations";
import { RAGInfoPanel } from "@/lib/components/chat/rag/RAGInfoPanel";
import { Sources } from "@/lib/components/web/Sources";
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

interface FileInfo {
    name: string;
    mimeType?: string;
}

interface ArtifactRef {
    name: string;
    status?: string;
}

// Part types for preserving render order
type MessagePart = { kind: "text"; text: string } | { kind: "file"; file: FileInfo } | { kind: "artifact"; artifact: ArtifactRef };

// Regex to match __EMBED_SIGNAL_xxx__ placeholders
const EMBED_SIGNAL_REGEX = /__EMBED_SIGNAL_[a-f0-9]+__/g;

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
            await forkSharedChat(shareId);
            // Navigate to the main chat view and trigger session refresh
            navigate(`/chat`);
            setTimeout(() => {
                window.dispatchEvent(new CustomEvent("new-chat-session"));
            }, 100);
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

            // Extract RAG data from task_metadata
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

    // Parse message bubbles from tasks - preserving part order for proper rendering
    const messages = useMemo(() => {
        if (!session) return [];

        const result: Array<{
            type: string;
            parts: MessagePart[];
            timestamp?: number;
            taskId: string;
            isLastInTask: boolean;
            senderDisplayName?: string;
            senderEmail?: string;
        }> = [];

        for (const task of session.tasks) {
            try {
                const taskId = task.workflow_task_id || task.id;

                const bubbles = typeof task.message_bubbles === "string" ? JSON.parse(task.message_bubbles) : task.message_bubbles;

                if (Array.isArray(bubbles)) {
                    (bubbles as MessageBubble[]).forEach((bubble: MessageBubble, index: number) => {
                        const parts: MessagePart[] = [];

                        // First, add uploadedFiles for user messages (they appear before text)
                        if (bubble.uploadedFiles && Array.isArray(bubble.uploadedFiles)) {
                            for (const f of bubble.uploadedFiles) {
                                const fileObj = f as { name?: string; filename?: string; mimeType?: string; mime_type?: string };
                                parts.push({
                                    kind: "file",
                                    file: {
                                        name: fileObj.name || fileObj.filename || "Attached file",
                                        mimeType: fileObj.mimeType || fileObj.mime_type,
                                    },
                                });
                            }
                        }

                        // Process parts array to preserve order
                        if (bubble.parts && Array.isArray(bubble.parts)) {
                            for (const part of bubble.parts) {
                                const partObj = part as {
                                    kind?: string;
                                    text?: string;
                                    file?: { name?: string; filename?: string; mimeType?: string; mime_type?: string };
                                    artifact?: { name?: string; filename?: string; status?: string };
                                };
                                if (partObj.kind === "text" && partObj.text) {
                                    const cleanedText = partObj.text.replace(EMBED_SIGNAL_REGEX, "").trim();
                                    if (cleanedText) {
                                        parts.push({ kind: "text", text: cleanedText });
                                    }
                                } else if (partObj.kind === "file" && partObj.file) {
                                    parts.push({
                                        kind: "file",
                                        file: {
                                            name: partObj.file.name || "Attached file",
                                            mimeType: partObj.file.mimeType,
                                        },
                                    });
                                } else if (partObj.kind === "artifact") {
                                    const artifactData = partObj.artifact || partObj;
                                    const artifactName = (artifactData as { name?: string; filename?: string }).name || (artifactData as { name?: string; filename?: string }).filename || (partObj.file as { name?: string })?.name || "Artifact";
                                    parts.push({
                                        kind: "artifact",
                                        artifact: {
                                            name: artifactName,
                                            status: (artifactData as { status?: string }).status || "completed",
                                        },
                                    });
                                }
                            }
                        } else if (bubble.text) {
                            const cleanedText = bubble.text.replace(EMBED_SIGNAL_REGEX, "").trim();
                            if (cleanedText) {
                                parts.push({ kind: "text", text: cleanedText });
                            }
                        }

                        result.push({
                            type: bubble.type || "agent",
                            parts: parts,
                            timestamp: task.created_time,
                            taskId: taskId,
                            isLastInTask: index === bubbles.length - 1,
                            senderDisplayName: bubble.sender_display_name,
                            senderEmail: bubble.sender_email,
                        });
                    });
                }
            } catch (e) {
                console.error("Failed to parse message bubbles:", e);
            }
        }
        return result;
    }, [session]);

    // Check if there are any RAG sources to show
    const hasRagSources = ragData.length > 0;

    const toggleSidePanel = () => {
        setIsSidePanelCollapsed(!isSidePanelCollapsed);
    };

    const handleViewWorkflow = (taskId: string) => {
        setSelectedTaskId(taskId);
        setActiveSidePanelTab("workflow");
        setIsSidePanelCollapsed(false);
    };

    // Get RAG data for a specific task (for citation rendering)
    const getTaskRagData = (taskId: string): RAGSearchResult | undefined => {
        const taskRagEntries = ragData.filter(r => r.taskId === taskId);
        if (taskRagEntries.length === 0) return undefined;

        const allSources = taskRagEntries.flatMap(entry => entry.sources || []);

        const seenCitationIds = new Set<string>();
        const uniqueSources = allSources.filter(source => {
            const citationId = source.citationId;
            if (!citationId || seenCitationIds.has(citationId)) {
                return false;
            }
            seenCitationIds.add(citationId);
            return true;
        });

        const lastEntry = taskRagEntries[taskRagEntries.length - 1];
        return {
            ...lastEntry,
            sources: uniqueSources,
        };
    };

    // Handle citation click - open sources panel
    const handleCitationClick = () => {
        if (hasRagSources) {
            setActiveSidePanelTab("sources");
            setIsSidePanelCollapsed(false);
        }
    };

    // Render message content with citation support - preserving part order
    const renderMessageContent = (message: { type: string; parts: MessagePart[]; taskId: string }) => {
        const taskRagData = message.type !== "user" ? getTaskRagData(message.taskId) : undefined;

        return (
            <>
                {message.parts.map((part, idx) => {
                    if (part.kind === "text") {
                        const text = part.text;
                        if (!text || !text.trim()) return null;

                        if (message.type !== "user" && taskRagData) {
                            const citations = parseCitations(text, taskRagData);
                            if (citations.length > 0) {
                                return <TextWithCitations key={idx} text={text} citations={citations} onCitationClick={handleCitationClick} />;
                            }
                        }
                        return (
                            <p key={idx} className={CHAT_BUBBLE_MESSAGE_STYLES.paragraph}>
                                {text}
                            </p>
                        );
                    }

                    if (part.kind === "file") {
                        return (
                            <div key={idx} className="my-2">
                                <FileMessage filename={part.file.name} mimeType={part.file.mimeType} readOnly />
                            </div>
                        );
                    }

                    if (part.kind === "artifact") {
                        const fullArtifact = convertedArtifacts.find(a => a.filename === part.artifact.name);
                        if (fullArtifact) {
                            return (
                                <div key={idx} className="my-2">
                                    <ArtifactMessage
                                        status="completed"
                                        name={fullArtifact.filename}
                                        fileAttachment={{
                                            name: fullArtifact.filename,
                                            mime_type: fullArtifact.mime_type,
                                        }}
                                    />
                                </div>
                            );
                        }
                        return (
                            <div key={idx} className="my-2">
                                <ArtifactMessage
                                    status="completed"
                                    name={part.artifact.name}
                                    fileAttachment={{
                                        name: part.artifact.name,
                                    }}
                                />
                            </div>
                        );
                    }

                    return null;
                })}
            </>
        );
    };

    // Get sources element for a specific task (for stacked favicons display)
    const getSourcesElement = (taskId: string) => {
        const taskRagEntries = ragData.filter(r => r.taskId === taskId);
        if (taskRagEntries.length === 0) return null;

        const allSources = taskRagEntries.flatMap(entry => entry.sources || []);
        if (allSources.length === 0) return null;

        const sourcesToShow = allSources.filter(source => {
            const sourceType = source.sourceType || "web";
            if (sourceType === "image") {
                return source.sourceUrl || source.metadata?.link;
            }
            return true;
        });

        if (sourcesToShow.length === 0) return null;

        return <Sources ragMetadata={{ sources: sourcesToShow }} isDeepResearch={false} onDeepResearchClick={handleCitationClick} />;
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

    // Header buttons: Fork & Continue or Go to Chat (if owner)
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
                Create Personal Copy
            </Button>
        ),
    ].filter(Boolean) as React.ReactNode[];

    return (
        <SharedChatProvider artifacts={convertedArtifacts} ragData={ragData} sessionId={sessionIdForProvider} shareId={shareId || ""}>
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
                                                        // In shared views, all user messages are from the session owner - show as "received" (left-aligned)
                                                        const variant = "received";
                                                        return (
                                                            <div key={index} className="mb-4 flex flex-col">
                                                                {/* Sender attribution using shared MessageAttribution component */}
                                                                {message.type === "user" ? (
                                                                    <MessageAttribution type="user" name={message.senderDisplayName || message.senderEmail || "User"} userIndex={0} timestamp={message.timestamp} />
                                                                ) : (
                                                                    <MessageAttribution type="agent" name="AI Assistant" />
                                                                )}
                                                                <div className="ml-10">
                                                                    <ChatBubble variant={variant}>
                                                                        <ChatBubbleMessage variant={variant}>{renderMessageContent(message)}</ChatBubbleMessage>
                                                                    </ChatBubble>
                                                                </div>
                                                                {message.type !== "user" && message.isLastInTask && (
                                                                    <div className="mt-1 flex items-center justify-start gap-2">
                                                                        <ViewWorkflowButton onClick={() => handleViewWorkflow(message.taskId)} />
                                                                        {getSourcesElement(message.taskId)}
                                                                    </div>
                                                                )}
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
                                                        Create Personal Copy
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
