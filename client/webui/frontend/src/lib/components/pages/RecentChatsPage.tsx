import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useInView } from "react-intersection-observer";
import { useNavigate, Navigate } from "react-router-dom";
import { Loader2, Check, X } from "lucide-react";

import { api } from "@/lib/api";
import { useChatContext, useConfigContext, useTitleGeneration, useTitleAnimation } from "@/lib/hooks";
import type { Session } from "@/lib/types";
import { formatRelativeTime, formatTimestamp, cn } from "@/lib/utils";
import { ProjectBadge, SessionSearch, SessionActionMenu } from "@/lib/components/chat";
import { Header } from "@/lib/components/header";
import { EmptyState } from "@/lib/components/common/EmptyState";
import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";

export interface PaginatedSessionsResponse {
    data: Session[];
    meta: {
        pagination: {
            pageNumber: number;
            count: number;
            pageSize: number;
            nextPage: number | null;
            totalPages: number;
        };
    };
}

interface SessionNameProps {
    session: Session;
    respondingSessionId: string | null;
    isSelected: boolean;
}

const SessionName: React.FC<SessionNameProps> = ({ session, respondingSessionId, isSelected }) => {
    const { autoTitleGenerationEnabled } = useConfigContext();

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

    const animationClass = useMemo(() => {
        if (isGenerating || isAnimating) {
            if (isWaitingForTitle) {
                return "animate-pulse-slow";
            }
            return "animate-pulse opacity-50";
        }
        if (isWaitingForTitle) {
            return "animate-pulse-slow";
        }
        return "opacity-100";
    }, [isWaitingForTitle, isAnimating, isGenerating]);

    return (
        <span title={animatedName} className={cn("truncate text-sm font-bold text-(--primary-text-wMain) transition-opacity duration-300", isSelected && "font-semibold", animationClass)}>
            {animatedName}
        </span>
    );
};

export const RecentChatsPage: React.FC = () => {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, updateSessionName, openSessionDeleteModal, addNotification, currentTaskId } = useChatContext();
    const { persistenceEnabled, configFeatureEnablement } = useConfigContext();
    const { generateTitle } = useTitleGeneration();
    const inputRef = useRef<HTMLInputElement>(null);

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

    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const [currentPage, setCurrentPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const [regeneratingTitleForSession, setRegeneratingTitleForSession] = useState<string | null>(null);

    const { ref: loadMoreRef, inView } = useInView({
        threshold: 0,
        triggerOnce: false,
    });

    const fetchSessions = useCallback(async (pageNumber: number = 1, append: boolean = false) => {
        setIsLoading(true);

        try {
            const result: PaginatedSessionsResponse = await api.webui.get(`/api/v1/sessions?pageNumber=${pageNumber}&pageSize=20`);

            if (append) {
                setSessions(prev => [...prev, ...result.data]);
            } else {
                setSessions(result.data);
            }

            setHasMore(result.meta.pagination.nextPage !== null);
            setCurrentPage(pageNumber);
        } catch (error) {
            console.error("An error occurred while fetching sessions:", error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSessions(1, false);

        const handleNewSession = () => {
            fetchSessions(1, false);
        };

        const handleSessionUpdated = (event: CustomEvent) => {
            const { sessionId } = event.detail;
            setSessions(prevSessions => {
                const updatedSession = prevSessions.find(s => s.id === sessionId);
                if (updatedSession) {
                    const otherSessions = prevSessions.filter(s => s.id !== sessionId);
                    return [updatedSession, ...otherSessions];
                }
                return prevSessions;
            });
        };

        const handleTitleUpdated = async (event: Event) => {
            const customEvent = event as CustomEvent;
            const { sessionId: updatedSessionId } = customEvent.detail;

            try {
                const sessionData = await api.webui.get(`/api/v1/sessions/${updatedSessionId}`);
                const updatedSession = sessionData?.data;

                if (updatedSession) {
                    setSessions(prevSessions => {
                        return prevSessions.map(s => (s.id === updatedSessionId ? { ...s, name: updatedSession.name } : s));
                    });
                }
            } catch (error) {
                console.error("[RecentChatsPage] Error fetching updated session:", error);
                fetchSessions(1, false);
            }
        };

        const handleBackgroundTaskCompleted = () => {
            fetchSessions(1, false);
        };

        window.addEventListener("new-chat-session", handleNewSession);
        window.addEventListener("session-updated", handleSessionUpdated as EventListener);
        window.addEventListener("session-title-updated", handleTitleUpdated);
        window.addEventListener("background-task-completed", handleBackgroundTaskCompleted);

        return () => {
            window.removeEventListener("new-chat-session", handleNewSession);
            window.removeEventListener("session-updated", handleSessionUpdated as EventListener);
            window.removeEventListener("session-title-updated", handleTitleUpdated);
            window.removeEventListener("background-task-completed", handleBackgroundTaskCompleted);
        };
    }, [fetchSessions]);

    // Periodic refresh when there are sessions with running background tasks
    useEffect(() => {
        const hasBackgroundTasks = sessions.some(s => s.hasRunningBackgroundTask);

        if (!hasBackgroundTasks) {
            return;
        }

        const intervalId = setInterval(() => {
            fetchSessions(1, false);
        }, 10000);

        return () => {
            clearInterval(intervalId);
        };
    }, [sessions, fetchSessions]);

    useEffect(() => {
        if (inView && hasMore && !isLoading) {
            fetchSessions(currentPage + 1, true);
        }
    }, [inView, hasMore, isLoading, currentPage, fetchSessions]);

    useEffect(() => {
        if (editingSessionId && inputRef.current) {
            inputRef.current.focus();
        }
    }, [editingSessionId]);

    const handleSessionClick = async (session: Session) => {
        if (editingSessionId !== session.id) {
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

    const handleRenameWithAI = useCallback(
        async (session: Session) => {
            if (regeneratingTitleForSession) {
                addNotification?.("AI rename already in progress", "info");
                return;
            }

            setRegeneratingTitleForSession(session.id);

            try {
                const data = await api.webui.get(`/api/v1/sessions/${session.id}/chat-tasks`);
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
                        if (text.trim()) {
                            allMessages.push(text.trim());
                        }
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
            } catch (error) {
                console.error("Error regenerating title:", error);
                addNotification?.(`Failed to regenerate title: ${error instanceof Error ? error.message : "Unknown error"}`, "warning");
            } finally {
                setRegeneratingTitleForSession(null);
            }
        },
        [generateTitle, addNotification, regeneratingTitleForSession]
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

    // Filter sessions by selected project
    const filteredSessions = useMemo(() => {
        if (selectedProject === "all") {
            return sessions;
        }
        if (selectedProject === "(No Project)") {
            return sessions.filter(session => !session.projectName);
        }
        return sessions.filter(session => session.projectName === selectedProject);
    }, [sessions, selectedProject]);

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
            <Header title="Recent Chats" />

            <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-8 py-6">
                {/* Search and Filter Bar */}
                <div className="flex items-center gap-4">
                    <div className="flex-1">
                        <SessionSearch onSessionSelect={handleSessionSelect} projectId={selectedProjectId} />
                    </div>

                    {persistenceEnabled && projectNames.length > 0 && (
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

                {/* Sessions Grid */}
                {filteredSessions.length > 0 && (
                    <div className="flex flex-col gap-2">
                        {filteredSessions.map(session => (
                            <div key={session.id} className="group relative h-[75px] rounded-lg border p-4 transition-colors hover:bg-(--primary-w10)">
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
                                            <span className="text-xs font-normal text-(--secondary-text-wMain)" title={formatTimestamp(session.updatedTime)}>
                                                Last message {formatRelativeTime(session.updatedTime)}
                                            </span>
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
                                                isRegeneratingTitle={regeneratingTitleForSession === session.id}
                                                triggerClassName=""
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* Empty States */}
                {filteredSessions.length === 0 && sessions.length > 0 && !isLoading && <EmptyState variant="noImage" title="No sessions found for this project" subtitle="Try selecting a different project filter" />}

                {sessions.length === 0 && !isLoading && <EmptyState variant="noImage" title="No chat sessions available" subtitle="Start a new chat to create your first session" />}

                {/* Infinite Scroll Loader */}
                {hasMore && (
                    <div ref={loadMoreRef} className="flex justify-center py-4">
                        {isLoading && <Spinner size="small" variant="muted" />}
                    </div>
                )}
            </div>
        </div>
    );
};
