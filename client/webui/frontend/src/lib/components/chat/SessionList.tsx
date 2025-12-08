import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useInView } from "react-intersection-observer";
import { useNavigate } from "react-router-dom";

import { Trash2, Check, X, Pencil, MessageCircle, FolderInput, MoreHorizontal, PanelsTopLeft, Loader2 } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { fetchJsonWithError, fetchWithError, getErrorMessage } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Spinner } from "@/lib/components/ui/spinner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { SessionSearch } from "@/lib/components/chat/SessionSearch";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/lib/components/ui/dropdown-menu";
import type { Project, Session } from "@/lib/types";

interface PaginatedSessionsResponse {
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

interface SessionListProps {
    projects?: Project[];
}

export const SessionList: React.FC<SessionListProps> = ({ projects = [] }) => {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, updateSessionName, openSessionDeleteModal, addNotification, displayError } = useChatContext();
    const { configServerUrl, persistenceEnabled } = useConfigContext();
    const inputRef = useRef<HTMLInputElement>(null);

    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const [currentPage, setCurrentPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedProject, setSelectedProject] = useState<string>("all");
    const [isMoveDialogOpen, setIsMoveDialogOpen] = useState(false);
    const [sessionToMove, setSessionToMove] = useState<Session | null>(null);

    const { ref: loadMoreRef, inView } = useInView({
        threshold: 0,
        triggerOnce: false,
    });

    const fetchSessions = useCallback(
        async (pageNumber: number = 1, append: boolean = false) => {
            setIsLoading(true);
            const url = `${configServerUrl}/api/v1/sessions?pageNumber=${pageNumber}&pageSize=20`;

            try {
                const result: PaginatedSessionsResponse = await fetchJsonWithError(url);

                if (append) {
                    setSessions(prev => [...prev, ...result.data]);
                } else {
                    setSessions(result.data);
                }

                // Use metadata to determine if there are more pages
                setHasMore(result.meta.pagination.nextPage !== null);
                setCurrentPage(pageNumber);
            } catch (error) {
                console.error("An error occurred while fetching sessions:", error);
            } finally {
                setIsLoading(false);
            }
        },
        [configServerUrl]
    );

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
        const handleBackgroundTaskCompleted = () => {
            // Refresh session list when background task completes to update indicators
            fetchSessions(1, false);
        };
        window.addEventListener("new-chat-session", handleNewSession);
        window.addEventListener("session-updated", handleSessionUpdated as EventListener);
        window.addEventListener("background-task-completed", handleBackgroundTaskCompleted);
        return () => {
            window.removeEventListener("new-chat-session", handleNewSession);
            window.removeEventListener("session-updated", handleSessionUpdated as EventListener);
            window.removeEventListener("background-task-completed", handleBackgroundTaskCompleted);
        };
    }, [fetchSessions]);

    // Periodic refresh when there are sessions with running background tasks
    // This is necessary to detect task completion when user is on a different session
    useEffect(() => {
        const hasBackgroundTasks = sessions.some(s => s.hasRunningBackgroundTask);

        if (!hasBackgroundTasks) {
            return; // No background tasks, no need to poll
        }

        const intervalId = setInterval(() => {
            fetchSessions(1, false);
        }, 10000); // Check every 10 seconds

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

    const handleSessionClick = async (sessionId: string) => {
        if (editingSessionId !== sessionId) {
            await handleSwitchSession(sessionId);
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

            // Clear editing state
            setEditingSessionId(null);

            // Update backend (this will trigger new-chat-session event which refetches)
            await updateSessionName(sessionIdToUpdate, newName);
        }
    };

    const handleDeleteClick = (session: Session) => {
        openSessionDeleteModal(session);
    };

    const handleMoveClick = (session: Session) => {
        setSessionToMove(session);
        setIsMoveDialogOpen(true);
    };
    const handleGoToProject = (session: Session) => {
        if (!session.projectId) return;

        // Navigate to projects page with the project ID
        navigate(`/projects/${session.projectId}`);
    };

    const handleMoveConfirm = async (targetProjectId: string | null) => {
        if (!sessionToMove) return;

        try {
            await fetchWithError(`${configServerUrl}/api/v1/sessions/${sessionToMove.id}/project`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ projectId: targetProjectId }),
            });

            // Update local state
            setSessions(prevSessions =>
                prevSessions.map(s =>
                    s.id === sessionToMove.id
                        ? {
                              ...s,
                              projectId: targetProjectId,
                              projectName: targetProjectId ? projects.find(p => p.id === targetProjectId)?.name || null : null,
                          }
                        : s
                )
            );

            // Dispatch event to notify other components (like ProjectChatsSection) to refresh
            if (typeof window !== "undefined") {
                window.dispatchEvent(
                    new CustomEvent("session-moved", {
                        detail: {
                            sessionId: sessionToMove.id,
                            projectId: targetProjectId,
                        },
                    })
                );
            }

            addNotification?.("Session moved successfully", "success");
            setIsMoveDialogOpen(false);
            setSessionToMove(null);
        } catch (error) {
            displayError({ title: "Failed to Move Session", error: getErrorMessage(error, "An unknown error occurred while moving the session.") });
        }
    };

    const formatSessionDate = (dateString: string) => {
        return formatTimestamp(dateString);
    };

    const getSessionDisplayName = (session: Session) => {
        if (session.name && session.name.trim()) {
            return session.name;
        }
        // Generate a short, readable identifier from the session ID
        const sessionId = session.id;
        if (sessionId.startsWith("web-session-")) {
            // Extract the UUID part and create a short identifier
            const uuid = sessionId.replace("web-session-", "");
            const shortId = uuid.substring(0, 8);
            return `Chat ${shortId}`;
        }
        // Fallback for other ID formats
        return `Session ${sessionId.substring(0, 8)}`;
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
        const project = projects.find(p => p.name === selectedProject);
        return project?.id || null;
    }, [selectedProject, projects]);

    return (
        <div className="flex h-full flex-col gap-4 py-6 pl-6">
            <div className="flex flex-col gap-4">
                {/* Session Search */}
                <div className="pr-4">
                    <SessionSearch onSessionSelect={handleSwitchSession} projectId={selectedProjectId} />
                </div>

                {/* Project Filter - Only show when persistence is enabled */}
                {persistenceEnabled && projectNames.length > 0 && (
                    <div className="flex items-center gap-2 pr-4">
                        <label className="text-sm font-medium">Project:</label>
                        <Select value={selectedProject} onValueChange={setSelectedProject}>
                            <SelectTrigger className="flex-1 rounded-md">
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

            <div className="flex-1 overflow-y-auto">
                {filteredSessions.length > 0 && (
                    <ul>
                        {filteredSessions.map(session => (
                            <li key={session.id} className="group my-2 pr-4">
                                <div className={`flex items-center gap-2 rounded px-2 py-2 ${session.id === sessionId ? "bg-muted" : ""}`}>
                                    {editingSessionId === session.id ? (
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
                                    ) : (
                                        <button onClick={() => handleSessionClick(session.id)} className="min-w-0 flex-1 cursor-pointer text-left">
                                            <div className="flex items-center gap-2">
                                                <div className="flex min-w-0 flex-1 flex-col gap-1">
                                                    <div className="flex items-center gap-2">
                                                        <span className="truncate font-semibold">{getSessionDisplayName(session)}</span>
                                                        {session.hasRunningBackgroundTask && (
                                                            <Tooltip>
                                                                <TooltipTrigger asChild>
                                                                    <Loader2 className="text-primary h-4 w-4 flex-shrink-0 animate-spin" />
                                                                </TooltipTrigger>
                                                                <TooltipContent>Background task running</TooltipContent>
                                                            </Tooltip>
                                                        )}
                                                    </div>
                                                    <span className="text-muted-foreground truncate text-xs">{formatSessionDate(session.updatedTime)}</span>
                                                </div>
                                                {session.projectName && (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Badge variant="outline" className="bg-primary/10 border-primary/30 text-primary max-w-[120px] flex-shrink-0 justify-start px-2 py-0.5 text-xs font-semibold shadow-sm">
                                                                <span className="block truncate">{session.projectName}</span>
                                                            </Badge>
                                                        </TooltipTrigger>
                                                        <TooltipContent>{session.projectName}</TooltipContent>
                                                    </Tooltip>
                                                )}
                                            </div>
                                        </button>
                                    )}
                                    <div className="flex flex-shrink-0 items-center">
                                        {editingSessionId === session.id ? (
                                            <>
                                                <Button variant="ghost" size="sm" onClick={handleRename} className="h-8 w-8 p-0">
                                                    <Check size={16} />
                                                </Button>
                                                <Button variant="ghost" size="sm" onClick={() => setEditingSessionId(null)} className="h-8 w-8 p-0">
                                                    <X size={16} />
                                                </Button>
                                            </>
                                        ) : (
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={e => e.stopPropagation()}>
                                                        <MoreHorizontal size={16} />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48">
                                                    {session.projectId && (
                                                        <>
                                                            <DropdownMenuItem
                                                                onClick={e => {
                                                                    e.stopPropagation();
                                                                    handleGoToProject(session);
                                                                }}
                                                            >
                                                                <PanelsTopLeft size={16} className="mr-2" />
                                                                Go to Project
                                                            </DropdownMenuItem>
                                                            <DropdownMenuSeparator />
                                                        </>
                                                    )}
                                                    <DropdownMenuItem
                                                        onClick={e => {
                                                            e.stopPropagation();
                                                            handleEditClick(session);
                                                        }}
                                                    >
                                                        <Pencil size={16} className="mr-2" />
                                                        Rename
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem
                                                        onClick={e => {
                                                            e.stopPropagation();
                                                            handleMoveClick(session);
                                                        }}
                                                    >
                                                        <FolderInput size={16} className="mr-2" />
                                                        Move to Project
                                                    </DropdownMenuItem>
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem
                                                        onClick={e => {
                                                            e.stopPropagation();
                                                            handleDeleteClick(session);
                                                        }}
                                                    >
                                                        <Trash2 size={16} className="mr-2" />
                                                        Delete
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        )}
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
                {filteredSessions.length === 0 && sessions.length > 0 && !isLoading && (
                    <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                        <MessageCircle className="mx-auto mb-4 h-12 w-12" />
                        No sessions found for this project
                    </div>
                )}
                {sessions.length === 0 && !isLoading && (
                    <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                        <MessageCircle className="mx-auto mb-4 h-12 w-12" />
                        No chat sessions available
                    </div>
                )}
                {hasMore && (
                    <div ref={loadMoreRef} className="flex justify-center py-4">
                        {isLoading && <Spinner size="small" variant="muted" />}
                    </div>
                )}
            </div>

            <MoveSessionDialog
                isOpen={isMoveDialogOpen}
                onClose={() => {
                    setIsMoveDialogOpen(false);
                    setSessionToMove(null);
                }}
                onConfirm={handleMoveConfirm}
                session={sessionToMove}
                projects={projects}
                currentProjectId={sessionToMove?.projectId}
            />
        </div>
    );
};
