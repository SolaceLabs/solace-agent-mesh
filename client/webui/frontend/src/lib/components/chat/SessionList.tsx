import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useInView } from "react-intersection-observer";

import { Trash2, Check, X, Pencil, MessageCircle, FolderInput, MoreHorizontal, PanelsTopLeft } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Spinner } from "@/lib/components/ui/spinner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { MoveSessionDialog } from "@/lib/components/chat/MoveSessionDialog";
import { SessionSearch } from "@/lib/components/chat/SessionSearch";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/lib/components/ui/dropdown-menu";
import type { Session } from "@/lib/types";
import type { Project } from "@/lib/types/projects";

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
    const { sessionId, handleSwitchSession, updateSessionName, openSessionDeleteModal, addNotification } = useChatContext();
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
            const pageSize = 20;

            const url = `${configServerUrl}/api/v1/sessions?pageNumber=${pageNumber}&pageSize=${pageSize}`;

            try {
                const response = await authenticatedFetch(url);
                if (response.ok) {
                    const result: PaginatedSessionsResponse = await response.json();

                    if (append) {
                        setSessions(prev => [...prev, ...result.data]);
                    } else {
                        setSessions(result.data);
                    }

                    // Use metadata to determine if there are more pages
                    setHasMore(result.meta.pagination.nextPage !== null);
                    setCurrentPage(pageNumber);
                } else {
                    console.error(`Failed to fetch sessions: ${response.status} ${response.statusText}`);
                }
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
        window.addEventListener("new-chat-session", handleNewSession);
        window.addEventListener("session-updated", handleSessionUpdated as EventListener);
        return () => {
            window.removeEventListener("new-chat-session", handleNewSession);
            window.removeEventListener("session-updated", handleSessionUpdated as EventListener);
        };
    }, [fetchSessions]);

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
            
            // Update local state immediately for instant UI feedback
            setSessions(prevSessions =>
                prevSessions.map(s =>
                    s.id === sessionIdToUpdate
                        ? { ...s, name: newName }
                        : s
                )
            );
            
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

        // Dispatch event to navigate to projects page and select this project
        if (typeof window !== "undefined") {
            window.dispatchEvent(
                new CustomEvent("navigate-to-project", {
                    detail: {
                        projectId: session.projectId,
                    },
                })
            );
        }
    };


    const handleMoveConfirm = async (targetProjectId: string | null) => {
        if (!sessionToMove) return;

        try {
            const response = await authenticatedFetch(
                `${configServerUrl}/api/v1/sessions/${sessionToMove.id}/project`,
                {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ projectId: targetProjectId }),
                    credentials: "include",
                }
            );

            if (!response.ok) {
                throw new Error("Failed to move session");
            }

            // Update local state
            setSessions(prevSessions =>
                prevSessions.map(s =>
                    s.id === sessionToMove.id
                        ? {
                              ...s,
                              projectId: targetProjectId,
                              projectName: targetProjectId
                                  ? projects.find(p => p.id === targetProjectId)?.name || null
                                  : null,
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
            console.error("Failed to move session:", error);
            addNotification?.("Failed to move session", "error");
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

    // Get unique project names from sessions, sorted by most recent activity
    const projectNames = useMemo(() => {
        // Create a map of project name to most recent session update timestamp
        const projectLastActivity = new Map<string, number>();
        
        sessions.forEach(session => {
            if (session.projectName && session.updatedTime) {
                try {
                    // Convert ISO string to timestamp for reliable comparison
                    const timestamp = new Date(session.updatedTime).getTime();
                    if (!isNaN(timestamp)) {
                        const existingTimestamp = projectLastActivity.get(session.projectName);
                        if (!existingTimestamp || timestamp > existingTimestamp) {
                            projectLastActivity.set(session.projectName, timestamp);
                        }
                    }
                } catch (error) {
                    // If date parsing fails, skip this session
                    console.warn(`Failed to parse updatedTime for session ${session.id}:`, error);
                }
            }
        });
        
        // Sort projects by most recent activity (descending), then alphabetically as fallback
        return Array.from(projectLastActivity.entries())
            .sort((a, b) => {
                const timeDiff = b[1] - a[1];
                if (timeDiff !== 0) return timeDiff;
                return a[0].localeCompare(b[0]);
            })
            .map(([name]) => name);
    }, [sessions]);

    // Filter sessions by selected project
    const filteredSessions = useMemo(() => {
        if (selectedProject === "all") {
            return sessions;
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
            <div className="flex flex-col gap-3">
                {/* Session Search */}
                <div className="pr-4">
                    <SessionSearch
                        onSessionSelect={handleSwitchSession}
                        projectId={selectedProjectId}
                    />
                </div>

                <div className="text-lg">
                    Chat Session History
                </div>

                {/* Project Filter - Only show when persistence is enabled */}
                {persistenceEnabled && projectNames.length > 0 && (
                    <div className="flex items-center gap-2 pr-4">
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
            
            <div className="flex-1 overflow-y-auto">
                {filteredSessions.length > 0 && (
                    <ul>
                        {filteredSessions.map(session => (
                            <li key={session.id} className="group my-2 pr-4">
                                <div className={`flex items-center gap-2 rounded px-4 py-2 ${session.id === sessionId ? "bg-muted" : ""}`}>
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
                                            className="flex-1 min-w-0 bg-transparent focus:outline-none"
                                        />
                                    ) : (
                                        <button onClick={() => handleSessionClick(session.id)} className="flex-1 min-w-0 cursor-pointer text-left">
                                            <div className="flex items-center gap-2">
                                                <div className="flex flex-col gap-1 min-w-0 flex-1">
                                                    <span className="truncate font-semibold" title={getSessionDisplayName(session)}>
                                                        {getSessionDisplayName(session)}
                                                    </span>
                                                    <span className="text-muted-foreground text-xs truncate">{formatSessionDate(session.updatedTime)}</span>
                                                </div>
                                                {session.projectName && (
                                                    <Badge
                                                        variant="outline"
                                                        className="max-w-[120px] text-xs bg-primary/10 border-primary/30 text-primary font-semibold px-2 py-0.5 shadow-sm justify-start flex-shrink-0"
                                                    >
                                                        <span className="truncate block">{session.projectName}</span>
                                                    </Badge>
                                                )}
                                            </div>
                                        </button>
                                    )}
                                    <div className="flex items-center flex-shrink-0">
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
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
                                                        <MoreHorizontal size={16} />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48">
                                                    {session.projectId && (
                                                        <>
                                                            <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleGoToProject(session); }}>
                                                                <PanelsTopLeft size={16} className="mr-2" />
                                                                Go to Project
                                                            </DropdownMenuItem>
                                                            <DropdownMenuSeparator />
                                                        </>
                                                    )}
                                                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleEditClick(session); }}>
                                                        <Pencil size={16} className="mr-2" />
                                                        Rename
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleMoveClick(session); }}>
                                                        <FolderInput size={16} className="mr-2" />
                                                        Move to Project
                                                    </DropdownMenuItem>
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDeleteClick(session); }}>
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
