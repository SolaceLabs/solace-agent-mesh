import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { useInView } from "react-intersection-observer";

import { Trash2, Check, X, Pencil, MessageCircle, Filter } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Spinner } from "@/lib/components/ui/spinner";
import type { Session } from "@/lib/types";

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

export const SessionList: React.FC = () => {
    const { sessionId, handleSwitchSession, updateSessionName, openSessionDeleteModal } = useChatContext();
    const { configServerUrl } = useConfigContext();
    const inputRef = useRef<HTMLInputElement>(null);

    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const [currentPage, setCurrentPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedProject, setSelectedProject] = useState<string | null>(null);

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

    // Get unique project names from sessions
    const projectNames = useMemo(() => {
        const names = new Set<string>();
        sessions.forEach(session => {
            if (session.projectName) {
                names.add(session.projectName);
            }
        });
        return Array.from(names).sort();
    }, [sessions]);

    // Filter sessions by selected project
    const filteredSessions = useMemo(() => {
        if (!selectedProject) {
            return sessions;
        }
        return sessions.filter(session => session.projectName === selectedProject);
    }, [sessions, selectedProject]);

    return (
        <div className="flex h-full flex-col gap-4 py-6 pl-6">
            <div className="flex flex-col gap-3">
                <div className="text-lg">
                    Chat Session History
                </div>
                
                {/* Project Filter */}
                {projectNames.length > 0 && (
                    <div className="flex flex-wrap gap-2 pr-4">
                        <Badge
                            variant={selectedProject === null ? "default" : "outline"}
                            className="cursor-pointer hover:bg-accent transition-colors"
                            onClick={() => setSelectedProject(null)}
                        >
                            <Filter className="mr-1" size={12} />
                            All Chats
                        </Badge>
                        {projectNames.map(projectName => (
                            <Badge
                                key={projectName}
                                variant={selectedProject === projectName ? "default" : "outline"}
                                className="cursor-pointer hover:bg-accent transition-colors"
                                onClick={() => setSelectedProject(projectName)}
                            >
                                {projectName}
                            </Badge>
                        ))}
                    </div>
                )}
            </div>
            
            <div className="flex-1 overflow-y-auto">
                {filteredSessions.length > 0 && (
                    <ul>
                        {filteredSessions.map(session => (
                            <li key={session.id} className="group my-2 pr-4">
                                <div className={`flex items-center justify-between rounded px-4 py-2 ${session.id === sessionId ? "bg-muted" : ""}`}>
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
                                            className="flex-grow bg-transparent focus:outline-none"
                                        />
                                    ) : (
                                        <button onClick={() => handleSessionClick(session.id)} className="flex-grow cursor-pointer text-left">
                                            <div className="flex max-w-50 flex-col gap-1">
                                                <div className="flex items-center gap-2">
                                                    <span className="truncate font-semibold" title={getSessionDisplayName(session)}>
                                                        {getSessionDisplayName(session)}
                                                    </span>
                                                    {session.projectName && (
                                                        <Badge
                                                            variant="outline"
                                                            className="text-xs bg-primary/10 border-primary/30 text-primary font-semibold px-2 py-0.5 shadow-sm"
                                                        >
                                                            {session.projectName}
                                                        </Badge>
                                                    )}
                                                </div>
                                                <span className="text-muted-foreground text-xs">{formatSessionDate(session.updatedTime)}</span>
                                            </div>
                                        </button>
                                    )}
                                    <div className="flex items-center opacity-0 transition-opacity group-hover:opacity-100">
                                        {editingSessionId === session.id ? (
                                            <>
                                                <Button variant="ghost" onClick={handleRename}>
                                                    <Check size={16} />
                                                </Button>
                                                <Button variant="ghost" onClick={() => setEditingSessionId(null)}>
                                                    <X size={16} />
                                                </Button>
                                            </>
                                        ) : (
                                            <>
                                                <Button variant="ghost" onClick={() => handleEditClick(session)}>
                                                    <Pencil size={16} />
                                                </Button>
                                                <Button variant="ghost" onClick={() => handleDeleteClick(session)}>
                                                    <Trash2 size={16} />
                                                </Button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
                {filteredSessions.length === 0 && sessions.length > 0 && !isLoading && (
                    <div className="text-muted-foreground flex h-full flex-col items-center justify-center text-sm">
                        <Filter className="mx-auto mb-4 h-12 w-12" />
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
        </div>
    );
};
