import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { useInView } from "react-intersection-observer";
import { useNavigate, Navigate } from "react-router-dom";
import { Loader2, Check, X, Plus, MessageCircle, CalendarClock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { useInfiniteSessions, useRenameSessionWithAI, sessionKeys } from "@/lib/api/sessions";
import { useChatContext, useConfigContext, useIsAutoTitleGenerationEnabled, useTitleGeneration, useTitleAnimation, useIsChatSharingEnabled } from "@/lib/hooks";
import type { Session } from "@/lib/types";
import { formatRelativeTime, formatTimestamp } from "@/lib/utils";
import { ProjectBadge, SessionSearch, SessionActionMenu, ChatSessionDeleteDialog, SessionIcon, sessionCardStyles, sessionTitleStyles } from "@/lib/components/chat";
import { ShareDialog } from "@/lib/components/share/ShareDialog";
import { Header } from "@/lib/components/header";
import { EmptyState } from "@/lib/components/common/EmptyState";
import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner, Tabs, TabsList, TabsTrigger, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";

const PAGE_SIZE = 20;
const BACKGROUND_TASK_POLL_MS = 10_000;

interface SessionNameProps {
    session: Session;
    respondingSessionId: string | null;
    isSelected: boolean;
}

const SessionName: React.FC<SessionNameProps> = ({ session, respondingSessionId, isSelected }) => {
    const autoTitleGenerationEnabled = useIsAutoTitleGenerationEnabled();

    const displayName = useMemo(() => {
        if (session.name && session.name.trim()) {
            return session.name;
        }
        return "New Chat";
    }, [session.name]);

    const { text: animatedName, isAnimating, isGenerating } = useTitleAnimation(displayName, session.id);

    const isWaitingForTitle = useMemo(() => {
        if (isGenerating) {
            return true;
        }
        if (!autoTitleGenerationEnabled) {
            return false;
        }
        const isNewChat = !session.name || session.name === "New Chat";
        const isThisSessionResponding = respondingSessionId === session.id;
        const hasBackgroundTaskWithNewTitle = session.hasRunningBackgroundTask && isNewChat;
        return (isThisSessionResponding && isNewChat) || hasBackgroundTaskWithNewTitle;
    }, [session.name, session.id, respondingSessionId, isGenerating, autoTitleGenerationEnabled, session.hasRunningBackgroundTask]);

    const animationVariant = useMemo((): "pulseGenerate" | "pulseWait" | "none" => {
        if (isGenerating || isAnimating) {
            return isWaitingForTitle ? "pulseGenerate" : "pulseWait";
        }
        if (isWaitingForTitle) return "pulseGenerate";
        return "none";
    }, [isWaitingForTitle, isAnimating, isGenerating]);

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <span className={sessionTitleStyles({ active: isSelected, animation: animationVariant })}>{animatedName}</span>
            </TooltipTrigger>
            <TooltipContent className="max-w-[480px]">{animatedName}</TooltipContent>
        </Tooltip>
    );
};

export const RecentChatsPage: React.FC = () => {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { sessionId, handleSwitchSession, handleNewSession, updateSessionName, openSessionDeleteModal, closeSessionDeleteModal, confirmSessionDelete, sessionToDelete, addNotification, currentTaskId, agentSessionRoutes } = useChatContext();
    const { persistenceEnabled, configFeatureEnablement } = useConfigContext();
    const { generateTitle } = useTitleGeneration();
    const chatSharingEnabled = useIsChatSharingEnabled();
    const inputRef = useRef<HTMLInputElement>(null);
    const [isShareDialogOpen, setIsShareDialogOpen] = useState(false);
    const [sessionToShare, setSessionToShare] = useState<Session | null>(null);

    // Track which session started the response
    const taskToSessionRef = useRef<Map<string, string>>(new Map());
    const [taskMapVersion, setTaskMapVersion] = useState(0);

    useEffect(() => {
        if (currentTaskId && !taskToSessionRef.current.has(currentTaskId)) {
            taskToSessionRef.current.set(currentTaskId, sessionId);
            setTaskMapVersion(v => v + 1);
        }
    }, [currentTaskId, sessionId]);

    const respondingSessionId = useMemo(() => {
        if (!currentTaskId) return null;
        return taskToSessionRef.current.get(currentTaskId) || null;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentTaskId, taskMapVersion]);

    const [activeTab, setActiveTab] = useState<"chat" | "scheduler">("chat");

    const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteSessions(PAGE_SIZE, activeTab);
    const sessions = useMemo(() => data?.pages.flatMap(page => page.data) ?? [], [data]);

    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const [regeneratingTitleForSession, setRegeneratingTitleForSession] = useState<string | null>(null);

    const { ref: loadMoreRef, inView } = useInView({
        threshold: 0,
        triggerOnce: false,
    });

    // Infinite scroll effect
    useEffect(() => {
        if (inView && hasNextPage && !isFetchingNextPage) {
            fetchNextPage();
        }
    }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

    // Background task polling
    useEffect(() => {
        const hasBackgroundTasks = sessions.some(s => s.hasRunningBackgroundTask);
        if (!hasBackgroundTasks) return;
        const id = setInterval(() => {
            queryClient.invalidateQueries({ queryKey: sessionKeys.lists() });
        }, BACKGROUND_TASK_POLL_MS);
        return () => clearInterval(id);
    }, [sessions, queryClient]);

    useEffect(() => {
        if (editingSessionId && inputRef.current) {
            inputRef.current.focus();
        }
    }, [editingSessionId]);

    const handleSessionClick = async (session: Session) => {
        if (editingSessionId === session.id) return;
        const route = (session.agentId && agentSessionRoutes?.[session.agentId]) || "/chat";
        if (route !== "/chat") {
            // Dispatch event for the host app to handle agent-specific routing
            // (e.g., Builder sessions navigate to /builder)
            window.dispatchEvent(
                new CustomEvent("agent-session-navigate", {
                    detail: { sessionId: session.id, route, agentId: session.agentId },
                })
            );
        } else {
            await handleSwitchSession(session.id);
            navigate("/chat");
        }
    };

    const handleEditClick = (session: Session) => {
        setEditingSessionId(session.id);
        setEditingSessionName(session.name || "");
    };

    const handleRename = async () => {
        if (editingSessionId) {
            const sessionIdToUpdate = editingSessionId;
            const newName = editingSessionName;

            setEditingSessionId(null);

            await updateSessionName(sessionIdToUpdate, newName);
        }
    };

    const handleDeleteClick = (session: Session) => {
        openSessionDeleteModal(session);
    };

    const handleMoveClick = (session: Session) => {
        window.dispatchEvent(new CustomEvent("open-move-session-dialog", { detail: { session } }));
    };

    const handleGoToProject = (session: Session) => {
        if (!session.projectId) return;
        navigate(`/projects/${session.projectId}`);
    };

    const handleShareClick = (session: Session) => {
        setSessionToShare(session);
        setIsShareDialogOpen(true);
    };

    const renameWithAIMutation = useRenameSessionWithAI();

    const handleRenameWithAI = useCallback(
        (session: Session) => {
            if (renameWithAIMutation.isPending) {
                addNotification?.("AI rename already in progress", "info");
                return;
            }

            setRegeneratingTitleForSession(session.id);

            renameWithAIMutation.mutate(session.id, {
                onSuccess: async data => {
                    const tasks = data.tasks || [];

                    if (tasks.length === 0) {
                        addNotification?.("No messages found in this session", "warning");
                        setRegeneratingTitleForSession(null);
                        return;
                    }

                    const allMessages: string[] = [];
                    for (const task of tasks) {
                        const messageBubbles = JSON.parse(task.messageBubbles);
                        for (const bubble of messageBubbles) {
                            const text = bubble.text || "";
                            if (text.trim()) allMessages.push(text.trim());
                        }
                    }

                    if (allMessages.length === 0) {
                        addNotification?.("No text content found in session", "warning");
                        setRegeneratingTitleForSession(null);
                        return;
                    }

                    const userMessages = allMessages.filter((_, idx) => idx % 2 === 0);
                    const agentMessages = allMessages.filter((_, idx) => idx % 2 === 1);
                    const userSummary = userMessages.slice(-3).join(" | ");
                    const agentSummary = agentMessages.slice(-3).join(" | ");

                    await generateTitle(session.id, userSummary, agentSummary, session.name || "New Chat", true);
                    setRegeneratingTitleForSession(null);
                },
                onError: error => {
                    console.error("Error regenerating title:", error);
                    addNotification?.(`Failed to regenerate title: ${error instanceof Error ? error.message : "Unknown error"}`, "warning");
                    setRegeneratingTitleForSession(null);
                },
            });
        },
        [renameWithAIMutation, generateTitle, addNotification]
    );

    const handleSessionSelect = async (sessionId: string) => {
        await handleSwitchSession(sessionId);
        navigate("/chat");
    };

    // Get unique project names from sessions, sorted alphabetically
    const projectNames = useMemo(() => {
        const uniqueProjectNames = new Set<string>();
        let hasUnassignedChats = false;

        sessions.forEach(session => {
            if (session.projectName) {
                uniqueProjectNames.add(session.projectName);
            } else {
                hasUnassignedChats = true;
            }
        });

        const sortedNames = Array.from(uniqueProjectNames).sort((a, b) => a.localeCompare(b));

        if (hasUnassignedChats) {
            sortedNames.unshift("(No Project)");
        }

        return sortedNames;
    }, [sessions]);

    // Filter sessions by source (client-side fallback until backend supports ?source filtering)
    // and then by selected project.
    const filteredSessions = useMemo(() => {
        let result = sessions;

        // Client-side source filter: scheduler tab shows only scheduler sessions,
        // chat tab excludes them.
        if (activeTab === "scheduler") {
            result = result.filter(session => session.source === "scheduler");
        } else {
            result = result.filter(session => session.source !== "scheduler");
        }

        if (selectedProject === "all") {
            return result;
        }
        if (selectedProject === "(No Project)") {
            return result.filter(session => !session.projectName);
        }
        return result.filter(session => session.projectName === selectedProject);
    }, [sessions, selectedProject, activeTab]);

    // Get the project ID for the selected project name (for search filtering)
    const selectedProjectId = useMemo(() => {
        if (selectedProject === "all") return null;
        const sessionWithProject = sessions.find(s => s.projectName === selectedProject);
        return sessionWithProject?.projectId || null;
    }, [selectedProject, sessions]);

    // Feature flag gate: redirect to /chat if newNavigation is not enabled
    if (!configFeatureEnablement?.newNavigation) {
        return <Navigate to="/chat" replace />;
    }

    return (
        <div className="flex h-full flex-col">
            <Header
                title="Recent Chats"
                buttons={[
                    <Button
                        key="new-chat"
                        onClick={() => {
                            navigate("/chat");
                            handleNewSession();
                        }}
                    >
                        <Plus size={16} className="mr-1" />
                        New Chat
                    </Button>,
                ]}
            />

            <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-8 py-6">
                {/* Tabs and Search/Filter Bar */}
                <div className="flex flex-col gap-4">
                    {/* Tabs: Chats / Scheduled Tasks */}
                    {configFeatureEnablement?.scheduler && (
                        <div className="flex justify-center">
                            <Tabs value={activeTab} onValueChange={value => setActiveTab(value as "chat" | "scheduler")}>
                                <TabsList className="bg-transparent p-0">
                                    <TabsTrigger value="chat" className="rounded-none rounded-l-md px-6">
                                        <MessageCircle className="h-4 w-4 shrink-0" />
                                        Chats
                                    </TabsTrigger>
                                    <TabsTrigger value="scheduler" className="rounded-none rounded-r-md border-l-0 px-6">
                                        <CalendarClock className="h-4 w-4 shrink-0" />
                                        Scheduled Tasks
                                    </TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>
                    )}

                    {/* Search and Filter Bar - only show when there are sessions */}
                    {sessions.length > 0 && (
                        <div className="flex items-center gap-4">
                            <div className="flex-1">
                                <SessionSearch onSessionSelect={handleSessionSelect} projectId={selectedProjectId} />
                            </div>

                            {persistenceEnabled && activeTab === "chat" && projectNames.length > 0 && (
                                <div className="flex items-center gap-2">
                                    <label className="text-sm font-medium">Project:</label>
                                    <Select value={selectedProject} onValueChange={setSelectedProject}>
                                        <SelectTrigger className="w-[200px] rounded-md">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Chats</SelectItem>
                                            {projectNames.map(projectName => (
                                                <SelectItem key={projectName} value={projectName}>
                                                    {projectName}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Sessions Grid */}
                {filteredSessions.length > 0 && (
                    <div className="flex flex-col gap-2">
                        {filteredSessions.map(session => (
                            <div key={session.id} className={sessionCardStyles({ active: session.id === sessionId })}>
                                {editingSessionId === session.id ? (
                                    <div className="flex items-center gap-2">
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={editingSessionName}
                                            onChange={e => setEditingSessionName(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === "Enter") {
                                                    e.preventDefault();
                                                    handleRename();
                                                }
                                            }}
                                            className="min-w-0 flex-1 bg-transparent focus:outline-none"
                                        />
                                        <div className="flex flex-shrink-0 items-center gap-1">
                                            <Button variant="ghost" size="sm" onClick={handleRename} className="h-8 w-8 p-0">
                                                <Check size={16} />
                                            </Button>
                                            <Button variant="ghost" size="sm" onClick={() => setEditingSessionId(null)} className="h-8 w-8 p-0">
                                                <X size={16} />
                                            </Button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex cursor-pointer items-center gap-4" onClick={() => handleSessionClick(session)}>
                                        <div className="flex min-w-0 flex-1 flex-col gap-1">
                                            <div className="flex items-center gap-2">
                                                <SessionIcon session={session} className="text-(--secondary-text-wMain)" />
                                                <SessionName session={session} respondingSessionId={respondingSessionId} isSelected={session.id === sessionId} />
                                                {session.hasRunningBackgroundTask && (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-(--primary-wMain)" />
                                                        </TooltipTrigger>
                                                        <TooltipContent>Background task running</TooltipContent>
                                                    </Tooltip>
                                                )}
                                            </div>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <div className="w-fit cursor-default text-xs font-normal text-(--secondary-text-wMain)">Last message {formatRelativeTime(session.updatedTime)}</div>
                                                </TooltipTrigger>
                                                <TooltipContent side="bottom">{formatTimestamp(session.updatedTime)}</TooltipContent>
                                            </Tooltip>
                                        </div>
                                        <div className="flex flex-shrink-0 items-center gap-2">
                                            {session.projectName && <ProjectBadge text={session.projectName} />}
                                            <SessionActionMenu
                                                session={session}
                                                onRename={handleEditClick}
                                                onRenameWithAI={handleRenameWithAI}
                                                onMove={handleMoveClick}
                                                onDelete={handleDeleteClick}
                                                onGoToProject={handleGoToProject}
                                                onShare={chatSharingEnabled ? handleShareClick : undefined}
                                                isRegeneratingTitle={regeneratingTitleForSession === session.id}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* Empty States */}
                {filteredSessions.length === 0 && sessions.length > 0 && !isFetchingNextPage && selectedProject !== "all" && (
                    <EmptyState variant="noImage" title="No sessions found for this project" subtitle="Try selecting a different project filter" />
                )}

                {filteredSessions.length === 0 && (sessions.length === 0 || selectedProject === "all") && !isFetchingNextPage && (
                    <EmptyState
                        variant="noImage"
                        title={activeTab === "scheduler" ? "No scheduled task sessions" : "No chat sessions available"}
                        subtitle={activeTab === "scheduler" ? "Sessions from scheduled tasks will appear here" : "Start a new chat to create your first session"}
                        buttons={
                            activeTab === "chat"
                                ? [
                                      {
                                          icon: <Plus size={16} />,
                                          text: "New Chat",
                                          variant: "default" as const,
                                          onClick: () => {
                                              navigate("/chat");
                                              handleNewSession();
                                          },
                                      },
                                  ]
                                : []
                        }
                    />
                )}

                {/* Infinite Scroll Loader */}
                {hasNextPage && (
                    <div ref={loadMoreRef} className="flex justify-center py-4">
                        {isFetchingNextPage && <Spinner size="small" variant="muted" />}
                    </div>
                )}
            </div>
            <ChatSessionDeleteDialog open={!!sessionToDelete} onCancel={closeSessionDeleteModal} onConfirm={confirmSessionDelete} sessionName={sessionToDelete?.name || ""} />
            {sessionToShare && (
                <ShareDialog
                    sessionId={sessionToShare.id}
                    sessionTitle={sessionToShare.name || "Untitled Chat"}
                    open={isShareDialogOpen}
                    onOpenChange={open => {
                        setIsShareDialogOpen(open);
                        if (!open) {
                            setSessionToShare(null);
                        }
                    }}
                />
            )}
        </div>
    );
};
