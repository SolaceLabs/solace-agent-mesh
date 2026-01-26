/**
 * SharedSessionPage - Public view of a shared chat session
 */

import { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, Globe, Building2, AlertCircle, FileText, Network, PanelRightIcon, Link2 } from "lucide-react";
import { Button, Spinner, Tabs, TabsList, TabsTrigger, TabsContent, ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/lib/components/ui";
import { ViewWorkflowButton } from "@/lib/components/ui/ViewWorkflowButton";
import { viewSharedSession } from "@/lib/api/shareApi";
import type { SharedSessionView } from "@/lib/types/share";
import type { MessageBubble } from "@/lib/types/storage";
import type { RAGSearchResult } from "@/lib/types";
import { SharedArtifactPanel } from "@/lib/components/share/SharedArtifactPanel";
import { SharedWorkflowPanel } from "@/lib/components/share/SharedWorkflowPanel";
import { TextWithCitations } from "@/lib/components/chat/Citation";
import { parseCitations } from "@/lib/utils/citations";
import { RAGInfoPanel } from "@/lib/components/chat/rag/RAGInfoPanel";
import { Sources } from "@/lib/components/web/Sources";

export function SharedSessionPage() {
    const { shareId } = useParams<{ shareId: string }>();
    const navigate = useNavigate();
    const [session, setSession] = useState<SharedSessionView | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSidePanelCollapsed, setIsSidePanelCollapsed] = useState(false);
    const [activeSidePanelTab, setActiveSidePanelTab] = useState<"files" | "workflow" | "sources">("files");
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

    useEffect(() => {
        if (shareId) {
            loadSharedSession(shareId);
        }
    }, [shareId]);

    const loadSharedSession = async (id: string) => {
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
    };

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

    // Parse message bubbles from tasks
    const messages = useMemo(() => {
        if (!session) return [];

        const result: Array<{
            type: string;
            text: string;
            timestamp?: number;
            taskId: string;
            isLastInTask: boolean;
        }> = [];

        for (const task of session.tasks) {
            try {
                const bubbles = typeof task.message_bubbles === "string" ? JSON.parse(task.message_bubbles) : task.message_bubbles;

                if (Array.isArray(bubbles)) {
                    (bubbles as MessageBubble[]).forEach((bubble: MessageBubble, index: number) => {
                        result.push({
                            type: bubble.type || "agent",
                            text: bubble.text || "",
                            timestamp: task.created_time,
                            // Use workflow_task_id for workflow lookup (A2A task ID), fallback to id
                            taskId: task.workflow_task_id || task.id,
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
                                    <SharedArtifactPanel artifacts={session.artifacts} />
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

    // Render message content with citation support
    const renderMessageContent = (message: { type: string; text: string; taskId: string }) => {
        // User messages don't have citations
        if (message.type === "user") {
            return <p className="whitespace-pre-wrap">{message.text}</p>;
        }

        // Get RAG data for this task
        const taskRagData = getTaskRagData(message.taskId);

        // Parse citations from the message text
        const citations = parseCitations(message.text, taskRagData);

        // If there are citations, use TextWithCitations
        if (citations.length > 0) {
            return <TextWithCitations text={message.text} citations={citations} onCitationClick={handleCitationClick} />;
        }

        // No citations - render as plain text
        return <p className="whitespace-pre-wrap">{message.text}</p>;
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

    return (
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
            <div className="min-h-0 flex-1">
                <ResizablePanelGroup direction="horizontal" autoSaveId="shared-session-side-panel" className="h-full">
                    {/* Messages panel */}
                    <ResizablePanel defaultSize={isSidePanelCollapsed ? 96 : 70} minSize={50} id="shared-session-messages-panel">
                        <main className="h-full overflow-y-auto p-6">
                            <div className="mx-auto max-w-3xl space-y-4">
                                {messages.length === 0 ? (
                                    <div className="text-muted-foreground py-12 text-center">
                                        <p>No messages in this session.</p>
                                    </div>
                                ) : (
                                    messages.map((message, index) => (
                                        <div key={index} className={`flex ${message.type === "user" ? "justify-end" : "justify-start"} mb-4 flex-col`}>
                                            <div className={`max-w-[80%] rounded-lg px-4 py-2 ${message.type === "user" ? "bg-primary text-primary-foreground ml-auto" : "bg-muted mr-auto"}`}>{renderMessageContent(message)}</div>
                                            {/* Show workflow button and sources outside the bubble for the last AI message in each task */}
                                            {message.type !== "user" && message.isLastInTask && (
                                                <div className="mt-1 flex items-center justify-start gap-2">
                                                    <ViewWorkflowButton onClick={() => handleViewWorkflow(message.taskId)} />
                                                    {getSourcesElement(message.taskId)}
                                                </div>
                                            )}
                                        </div>
                                    ))
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

            {/* Footer */}
            <footer className="text-muted-foreground border-t px-6 py-3 text-center text-sm">
                <p>This is a read-only view of a shared chat session.</p>
            </footer>
        </div>
    );
}
