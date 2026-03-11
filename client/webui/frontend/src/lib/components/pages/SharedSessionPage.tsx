/**
 * SharedSessionPage - Public view of a shared chat session
 */

import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, Globe, Building2, AlertCircle, FileText, Network, PanelRightIcon, Link2, PencilOff } from "lucide-react";
import { Button, Spinner, Tabs, TabsList, TabsTrigger, TabsContent, ResizablePanelGroup, ResizablePanel, ResizableHandle, ChatBubble, ChatBubbleMessage } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { viewSharedSession, downloadSharedArtifact } from "@/lib/api/shareApi";
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

export function SharedSessionPage() {
    const { shareId } = useParams<{ shareId: string }>();
    const navigate = useNavigate();
    const [session, setSession] = useState<SharedSessionView | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(false);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "workflow" | "sources">("files");
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

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

    useEffect(() => {
        if (shareId) {
            loadSharedSession(shareId);
        }
    }, [shareId, loadSharedSession]);

    const getAccessIcon = (accessType: string) => {
        switch (accessType) {
            case "public":
                return <Globe className="h-4 w-4" />;
            case "authenticated":
                return <Lock className="h-4 w-4" />;
            case "domain-restricted":
                return <Building2 className="h-4 w-4" />;
            default:
                return null;
        }
    };

    const getAccessLabel = (accessType: string) => {
        switch (accessType) {
            case "public":
                return "Public";
            case "authenticated":
                return "Authenticated";
            case "domain-restricted":
                return "Domain Restricted";
            default:
                return accessType;
        }
    };

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
            parts: MessagePart[]; // Preserve original part order
            timestamp?: number;
            taskId: string;
            isLastInTask: boolean;
        }> = [];

        for (const task of session.tasks) {
            try {
                // Use workflow_task_id for workflow lookup (A2A task ID), fallback to id
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
                                const partObj = part as { kind?: string; text?: string; file?: { name?: string; filename?: string; mimeType?: string; mime_type?: string }; artifact?: { name?: string; filename?: string; status?: string } };
                                if (partObj.kind === "text" && partObj.text) {
                                    // Remove __EMBED_SIGNAL_xxx__ placeholders from text
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
                                    // Handle both formats:
                                    // 1. Nested: { kind: "artifact", artifact: { name, status } }
                                    // 2. Flat: { kind: "artifact", name, status, file: { name, mime_type, uri } }
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
                            // Fallback: use bubble.text if no parts array
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

    // Check if there are artifacts to show
    const hasArtifacts = session && session.artifacts && session.artifacts.length > 0;

    const toggleSidePanel = () => {
        setIsSidePanelCollapsed(!isSidePanelCollapsed);
    };

    const handleViewWorkflow = (taskId: string) => {
        setSelectedTaskId(taskId);
        setActiveSidePanelTab("workflow");
        setIsSidePanelCollapsed(false);
    };

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Spinner size="large" variant="primary">
                    <p className="text-muted-foreground mt-4 text-sm">Loading shared session...</p>
                </Spinner>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-destructive h-16 w-16" />
                <h1 className="text-2xl font-semibold">Unable to View Session</h1>
                <p className="text-muted-foreground max-w-md text-center">{error}</p>
                <Button variant="outline" onClick={() => navigate("/")}>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Go to Home
                </Button>
            </div>
        );
    }

    if (!session) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-muted-foreground h-16 w-16" />
                <h1 className="text-2xl font-semibold">Session Not Found</h1>
                <p className="text-muted-foreground">This shared session may have been deleted or the link is invalid.</p>
                <Button variant="outline" onClick={() => navigate("/")}>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Go to Home
                </Button>
            </div>
        );
    }

    // Get RAG data for a specific task (for citation rendering)
    const getTaskRagData = (taskId: string): RAGSearchResult | undefined => {
        const taskRagEntries = ragData.filter(r => r.taskId === taskId);
        if (taskRagEntries.length === 0) return undefined;

        // Aggregate all sources from all matching RAG entries
        const allSources = taskRagEntries.flatMap(entry => entry.sources || []);

        // Deduplicate sources by citationId (keep the first occurrence)
        const seenCitationIds = new Set<string>();
        const uniqueSources = allSources.filter(source => {
            const citationId = source.citationId;
            if (!citationId || seenCitationIds.has(citationId)) {
                return false;
            }
            seenCitationIds.add(citationId);
            return true;
        });

        // Return the last entry as base with aggregated sources
        const lastEntry = taskRagEntries[taskRagEntries.length - 1];
        return {
            ...lastEntry,
            sources: uniqueSources,
        };
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
                                    <SharedWorkflowPanel taskEvents={session.task_events} selectedTaskId={selectedTaskId} onTaskSelect={setSelectedTaskId} />
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

    // Handle citation click - open sources panel
    const handleCitationClick = () => {
        if (hasRagSources) {
            setActiveSidePanelTab("sources");
            setIsSidePanelCollapsed(false);
        }
    };

    // Render message content with citation support - preserving part order
    const renderMessageContent = (message: { type: string; parts: MessagePart[]; taskId: string }) => {
        // Get RAG data for this task (for citations in agent messages)
        const taskRagData = message.type !== "user" ? getTaskRagData(message.taskId) : undefined;

        return (
            <>
                {message.parts.map((part, idx) => {
                    if (part.kind === "text") {
                        const text = part.text;
                        if (!text || !text.trim()) return null;

                        // For agent messages, check for citations
                        if (message.type !== "user" && taskRagData) {
                            const citations = parseCitations(text, taskRagData);
                            if (citations.length > 0) {
                                return <TextWithCitations key={idx} text={text} citations={citations} onCitationClick={handleCitationClick} />;
                            }
                        }
                        return (
                            <p key={idx} className="whitespace-pre-wrap">
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
                        // Find the full artifact info from the session artifacts
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
                        // Fallback if artifact not found in session artifacts
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

        // Aggregate all sources from all matching RAG entries
        const allSources = taskRagEntries.flatMap(entry => entry.sources || []);
        if (allSources.length === 0) return null;

        // Filter sources - for web search, include all web sources
        const sourcesToShow = allSources.filter(source => {
            const sourceType = source.sourceType || "web";
            // For images: include if they have a source link
            if (sourceType === "image") {
                return source.sourceUrl || source.metadata?.link;
            }
            return true;
        });

        if (sourcesToShow.length === 0) return null;

        return <Sources ragMetadata={{ sources: sourcesToShow }} isDeepResearch={false} onDeepResearchClick={handleCitationClick} />;
    };

    // Get session ID for the provider
    const sessionIdForProvider = session.tasks[0]?.session_id || session.share_id;

    return (
        <SharedChatProvider artifacts={convertedArtifacts} ragData={ragData} sessionId={sessionIdForProvider} shareId={shareId || ""}>
            <div className="flex h-screen flex-col">
                {/* Header */}
                <header className="border-b px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Button>
                            <div className="h-6 border-r" />
                            <div>
                                <h1 className="text-lg font-semibold">{session.title}</h1>
                                <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                    {getAccessIcon(session.access_type)}
                                    <span>{getAccessLabel(session.access_type)}</span>
                                    <span>•</span>
                                    <span>Shared on {new Date(session.created_time).toLocaleDateString()}</span>
                                    {hasArtifacts && (
                                        <>
                                            <span>•</span>
                                            <span>
                                                {session.artifacts.length} file{session.artifacts.length !== 1 ? "s" : ""}
                                            </span>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Main content with resizable panels - always show side panel */}
                <div className="relative min-h-0 flex-1 border-3 border-(--color-info-w30) bg-(--color-background-w20)">
                    {/* Read-Only Indicator */}
                    <div className="absolute top-0 left-1/2 z-10 flex h-8 -translate-x-1/2 items-center justify-center gap-2 rounded-br rounded-bl bg-(--color-info-w30) px-2">
                        <PencilOff className="h-4 w-4 text-(--color-info-w100)" />
                        <span className="text-xs text-(--color-info-w100)">Read-Only</span>
                    </div>
                    <ResizablePanelGroup direction="horizontal" autoSaveId="shared-session-side-panel" className="h-full">
                        {/* Messages panel */}
                        <ResizablePanel defaultSize={isSidePanelCollapsed ? 96 : 70} minSize={50} id="shared-session-messages-panel">
                            <main className="h-full overflow-y-auto bg-(--color-background-w20) p-6">
                                <div className="mx-auto max-w-3xl space-y-4">
                                    {messages.length === 0 ? (
                                        <div className="text-muted-foreground py-12 text-center">
                                            <p>No messages in this session.</p>
                                        </div>
                                    ) : (
                                        messages.map((message, index) => {
                                            const variant = message.type === "user" ? "sent" : "received";
                                            return (
                                                <div key={index} className="mb-4 flex flex-col">
                                                    <ChatBubble variant={variant}>
                                                        <ChatBubbleMessage variant={variant}>{renderMessageContent(message)}</ChatBubbleMessage>
                                                    </ChatBubble>
                                                    {/* Show workflow button and sources outside the bubble for the last AI message in each task */}
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
                        </ResizablePanel>

                        <ResizableHandle />

                        {/* Side panel - always visible */}
                        <ResizablePanel defaultSize={isSidePanelCollapsed ? 4 : 30} minSize={isSidePanelCollapsed ? 4 : 20} maxSize={isSidePanelCollapsed ? 4 : 50} id="shared-session-side-panel">
                            {renderSidePanel()}
                        </ResizablePanel>
                    </ResizablePanelGroup>
                </div>
            </div>
        </SharedChatProvider>
    );
}
