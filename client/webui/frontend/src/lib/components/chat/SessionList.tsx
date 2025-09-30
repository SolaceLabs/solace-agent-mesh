import React, { useEffect, useState, useRef, useCallback } from "react";
import { useInView } from "react-intersection-observer";

import { Trash2, Check, X, Pencil, MessageCircle } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Spinner } from "@/lib/components/ui/spinner";

interface Session {
    id: string;
    createdTime: string;
    updatedTime: string;
    name: string | null;
}

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
    const { handleSwitchSession, updateSessionName, openSessionDeleteModal } = useChatContext();
    const { configServerUrl } = useConfigContext();
    const inputRef = useRef<HTMLInputElement>(null);

    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const [currentPage, setCurrentPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(false);

    const { ref: loadMoreRef, inView } = useInView({
        threshold: 0,
        triggerOnce: false,
    });

    const fetchSessions = useCallback(async (pageNumber: number = 1, append: boolean = false) => {
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
    }, [configServerUrl]);

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
            await updateSessionName(editingSessionId, editingSessionName);
            setEditingSessionId(null);
            fetchSessions();
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

    return (
        <div className="flex h-full flex-col gap-4 py-6 pl-6">
            <div className="text-lg">Chat Session History</div>
            <div className="flex-1 overflow-y-auto">
                {sessions.length > 0 && (
                    <ul>
                        {sessions.map(session => (
                            <li key={session.id} className="group my-2 pr-4">
                                <div className="flex items-center justify-between rounded px-4 py-2 hover:bg-gray-200 dark:hover:bg-gray-700">
                                    {editingSessionId === session.id ? (
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={editingSessionName}
                                            onChange={e => setEditingSessionName(e.target.value)}
                                            onKeyDown={e => e.key === "Enter" && handleRename()}
                                            onBlur={handleRename}
                                            className="flex-grow bg-transparent focus:outline-none"
                                        />
                                    ) : (
                                        <button onClick={() => handleSessionClick(session.id)} className="flex-grow text-left">
                                            <div className="flex max-w-50 flex-col">
                                                <span className="truncate font-semibold" title={getSessionDisplayName(session)}>
                                                    {getSessionDisplayName(session)}
                                                </span>
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
