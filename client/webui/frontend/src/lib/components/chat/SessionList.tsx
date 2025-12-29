import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useInView } from "react-intersection-observer";
import { useNavigate } from "react-router-dom";

import { Trash2, Check, X, Pencil, MessageCircle, FolderInput, MoreHorizontal, PanelsTopLeft, Loader2 } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Spinner } from "@/lib/components/ui/spinner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { BatchMoveSessionDialog, BatchDeleteSessionDialog } from "@/lib/components/chat";
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

interface BatchOperationResponse {
    success: string[];
    failed: { id: string; reason: string }[];
    totalRequested: number;
    totalSuccess: number;
    totalFailed: number;
}

interface SessionListProps {
    projects?: Project[];
}

export const SessionList: React.FC<SessionListProps> = ({ projects = [] }) => {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, updateSessionName, openSessionDeleteModal, addNotification, displayError } = useChatContext();
    const { persistenceEnabled } = useConfigContext();
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

    // Multi-select state (Ctrl/Cmd+Click)
    const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(new Set());
    const [isBatchMoveDialogOpen, setIsBatchMoveDialogOpen] = useState(false);
    const [isBatchDeleteDialogOpen, setIsBatchDeleteDialogOpen] = useState(false);

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

            // Use metadata to determine if there are more pages
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

    // Handle click outside to clear selection
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            // Only clear if clicking outside the session list and not on a dialog or popover
            const target = e.target as HTMLElement;
            if (!target.closest("[data-session-list]") && !target.closest('[role="dialog"]') && !target.closest('[role="listbox"]') && !target.closest("[data-radix-popper-content-wrapper]")) {
                setSelectedSessionIds(new Set());
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Handle Escape key to clear selection
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === "Escape" && selectedSessionIds.size > 0) {
                setSelectedSessionIds(new Set());
            }
        };

        document.addEventListener("keydown", handleEscape);
        return () => document.removeEventListener("keydown", handleEscape);
    }, [selectedSessionIds.size]);

    const handleSessionClick = async (clickedSessionId: string, event: React.MouseEvent) => {
        if (editingSessionId === clickedSessionId) return;

        // Check for Ctrl (Windows/Linux) or Cmd (Mac) key
        const isMultiSelectClick = event.ctrlKey || event.metaKey;

        if (isMultiSelectClick) {
            // Multi-select click - add to selection
            setSelectedSessionIds(prev => {
                const newSet = new Set(prev);

                // If this is the first multi-select click and we have a current session,
                // include the current session in the selection
                if (newSet.size === 0 && sessionId && sessionId !== clickedSessionId) {
                    newSet.add(sessionId);
                }

                // Toggle the clicked session
                if (newSet.has(clickedSessionId)) {
                    newSet.delete(clickedSessionId);
                } else {
                    newSet.add(clickedSessionId);
                }
                return newSet;
            });
        } else {
            // Normal click - clear selection and switch session
            setSelectedSessionIds(new Set());
            await handleSwitchSession(clickedSessionId);
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
            await api.webui.patch(`/api/v1/sessions/${sessionToMove.id}/project`, { projectId: targetProjectId });

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

    const handleClearSelection = () => {
        setSelectedSessionIds(new Set());
    };

    const handleBatchMoveConfirm = async (targetProjectId: string | null) => {
        if (selectedSessionIds.size === 0) return;

        try {
            const result: BatchOperationResponse = await api.webui.post("/api/v1/sessions/batch/move", {
                sessionIds: Array.from(selectedSessionIds),
                projectId: targetProjectId,
            });

            // Update local state for successful moves
            if (result.success.length > 0) {
                setSessions(prevSessions =>
                    prevSessions.map(s =>
                        result.success.includes(s.id)
                            ? {
                                  ...s,
                                  projectId: targetProjectId,
                                  projectName: targetProjectId ? projects.find(p => p.id === targetProjectId)?.name || null : null,
                              }
                            : s
                    )
                );

                // Dispatch event to notify other components
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("sessions-batch-moved", {
                            detail: {
                                sessionIds: result.success,
                                projectId: targetProjectId,
                            },
                        })
                    );
                }
            }

            // Show notification
            if (result.totalFailed > 0) {
                addNotification?.(`Moved ${result.totalSuccess} of ${result.totalRequested} chats. ${result.totalFailed} failed.`, "warning");
            } else {
                addNotification?.(`Successfully moved ${result.totalSuccess} chat${result.totalSuccess > 1 ? "s" : ""}`, "success");
            }

            // Clear selection
            setSelectedSessionIds(new Set());
            setIsBatchMoveDialogOpen(false);
        } catch (error) {
            displayError({ title: "Failed to Move Chats", error: getErrorMessage(error, "An unknown error occurred while moving the chats.") });
        }
    };

    const handleBatchDeleteConfirm = async () => {
        if (selectedSessionIds.size === 0) return;

        try {
            const result: BatchOperationResponse = await api.webui.post("/api/v1/sessions/batch/delete", {
                sessionIds: Array.from(selectedSessionIds),
            });

            // Remove deleted sessions from local state
            if (result.success.length > 0) {
                setSessions(prevSessions => prevSessions.filter(s => !result.success.includes(s.id)));

                // Dispatch event to notify other components
                if (typeof window !== "undefined") {
                    window.dispatchEvent(
                        new CustomEvent("sessions-batch-deleted", {
                            detail: {
                                sessionIds: result.success,
                            },
                        })
                    );
                }
            }

            // Show notification
            if (result.totalFailed > 0) {
                addNotification?.(`Deleted ${result.totalSuccess} of ${result.totalRequested} chats. ${result.totalFailed} failed.`, "warning");
            } else {
                addNotification?.(`Successfully deleted ${result.totalSuccess} chat${result.totalSuccess > 1 ? "s" : ""}`, "success");
            }

            // Clear selection
            setSelectedSessionIds(new Set());
            setIsBatchDeleteDialogOpen(false);
        } catch (error) {
            displayError({ title: "Failed to Delete Chats", error: getErrorMessage(error, "An unknown error occurred while deleting the chats.") });
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

    const hasSelection = selectedSessionIds.size > 0;

    return (
        <div className="flex h-full flex-col gap-4 py-6 pl-6" data-session-list>
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

                {/* Batch action bar - appears when sessions are selected */}
                {hasSelection && (
                    <div className="bg-muted/50 flex items-center gap-2 rounded-md p-2 pr-4">
                        <span className="text-muted-foreground text-sm font-medium">{selectedSessionIds.size} selected</span>
                        <div className="flex-1" />
                        <Button variant="ghost" size="sm" onClick={handleClearSelection}>
                            Clear
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setIsBatchMoveDialogOpen(true)} className="gap-2">
                            <FolderInput size={16} />
                            Move
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => setIsBatchDeleteDialogOpen(true)} className="gap-2">
                            <Trash2 size={16} />
                            Delete
                        </Button>
                    </div>
                )}

                {/* Hint for multi-select */}
                {!hasSelection && filteredSessions.length > 1 && <div className="text-muted-foreground pr-4 text-xs">Tip: {navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+Click to select multiple chats</div>}
            </div>

            <div className="flex-1 overflow-y-auto">
                {filteredSessions.length > 0 && (
                    <ul>
                        {filteredSessions.map(session => {
                            const isSelected = selectedSessionIds.has(session.id);
                            const isCurrentSession = session.id === sessionId && !hasSelection;

                            return (
                                <li key={session.id} className="group my-2 pr-4">
                                    <div className={`flex items-center gap-2 rounded px-2 py-2 transition-colors ${isSelected ? "bg-primary/20 ring-primary/50 ring-1" : isCurrentSession ? "bg-muted" : "hover:bg-muted/50"}`}>
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
                                            <button onClick={e => handleSessionClick(session.id, e)} className="min-w-0 flex-1 cursor-pointer text-left">
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
                                            ) : !hasSelection ? (
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
                                            ) : null}
                                        </div>
                                    </div>
                                </li>
                            );
                        })}
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

            <BatchMoveSessionDialog isOpen={isBatchMoveDialogOpen} onClose={() => setIsBatchMoveDialogOpen(false)} onConfirm={handleBatchMoveConfirm} sessionCount={selectedSessionIds.size} projects={projects} />

            <BatchDeleteSessionDialog isOpen={isBatchDeleteDialogOpen} onClose={() => setIsBatchDeleteDialogOpen(false)} onConfirm={handleBatchDeleteConfirm} sessionCount={selectedSessionIds.size} />
        </div>
    );
};
