import React, { useEffect, useState, useCallback, useMemo } from "react";
import { ChevronDown, MessageCircle, MoreHorizontal, Pencil, Trash2, FolderInput } from "lucide-react";

import { useChatContext, useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import { formatTimestamp } from "@/lib/utils/format";
import { Button } from "@/lib/components/ui/button";
import { Spinner } from "@/lib/components/ui/spinner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/lib/components/ui/dropdown-menu";
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

interface RecentChatsListProps {
    /** Maximum number of items to show initially */
    maxItems?: number;
    /** Callback when "Show All" is clicked */
    onShowAll?: () => void;
    /** Project filter - "all" for all projects, "(No Project)" for unassigned, or project name */
    projectFilter?: string;
}

export const RecentChatsList: React.FC<RecentChatsListProps> = ({ maxItems = 5, onShowAll, projectFilter = "all" }) => {
    const { sessionId, handleSwitchSession } = useChatContext();
    const { configServerUrl } = useConfigContext();

    const [sessions, setSessions] = useState<Session[]>([]);
    const [isLoading, setIsLoading] = useState(false);

    const fetchSessions = useCallback(async () => {
        setIsLoading(true);
        // Fetch a bit more than maxItems to know if there are more
        const pageSize = maxItems + 1;

        const url = `${configServerUrl}/api/v1/sessions?pageNumber=1&pageSize=${pageSize}`;

        try {
            const response = await authenticatedFetch(url);
            if (response.ok) {
                const result: PaginatedSessionsResponse = await response.json();
                setSessions(result.data);
            } else {
                console.error(`Failed to fetch sessions: ${response.status} ${response.statusText}`);
            }
        } catch (error) {
            console.error("An error occurred while fetching sessions:", error);
        } finally {
            setIsLoading(false);
        }
    }, [configServerUrl, maxItems]);

    useEffect(() => {
        fetchSessions();

        const handleNewSession = () => {
            fetchSessions();
        };
        const handleSessionUpdated = () => {
            fetchSessions();
        };

        window.addEventListener("new-chat-session", handleNewSession);
        window.addEventListener("session-updated", handleSessionUpdated);

        return () => {
            window.removeEventListener("new-chat-session", handleNewSession);
            window.removeEventListener("session-updated", handleSessionUpdated);
        };
    }, [fetchSessions]);

    const handleSessionClick = async (clickedSessionId: string) => {
        // Navigate to chat page first
        if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("navigate-to-chat"));
        }
        await handleSwitchSession(clickedSessionId);
    };

    const formatSessionDate = (dateString: string) => {
        return formatTimestamp(dateString);
    };

    const getSessionDisplayName = (session: Session) => {
        if (session.name && session.name.trim()) {
            return session.name;
        }
        // Generate a short, readable identifier from the session ID
        const id = session.id;
        if (id.startsWith("web-session-")) {
            const uuid = id.replace("web-session-", "");
            const shortId = uuid.substring(0, 8);
            return `Chat ${shortId}`;
        }
        return `Session ${id.substring(0, 8)}`;
    };

    // Filter sessions by project
    const filteredSessions = useMemo(() => {
        if (projectFilter === "all") {
            return sessions;
        }
        if (projectFilter === "(No Project)") {
            return sessions.filter(session => !session.projectName);
        }
        return sessions.filter(session => session.projectName === projectFilter);
    }, [sessions, projectFilter]);

    // Only show up to maxItems from filtered sessions
    const displayedSessions = filteredSessions.slice(0, maxItems);
    const hasMore = filteredSessions.length > maxItems;

    if (isLoading && sessions.length === 0) {
        return (
            <div className="flex justify-center py-4">
                <Spinner size="small" variant="muted" />
            </div>
        );
    }

    if (filteredSessions.length === 0) {
        return (
            <div className="text-muted-foreground flex flex-col items-center justify-center py-4 text-sm">
                <MessageCircle className="mx-auto mb-2 h-8 w-8 opacity-50" />
                <span>{projectFilter === "all" ? "No recent chats" : "No chats in this project"}</span>
            </div>
        );
    }

    const handleDeleteClick = (session: Session) => {
        // Use the openSessionDeleteModal from context if available
        if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("open-session-delete-modal", { detail: { session } }));
        }
    };

    return (
        <div className="flex flex-col">
            <ul className="space-y-1">
                {displayedSessions.map(session => (
                    <li key={session.id} className="group">
                        <div className={`hover:bg-accent/50 flex items-center gap-1 rounded-md px-2 py-1.5 transition-colors ${session.id === sessionId ? "bg-accent" : ""}`}>
                            <button onClick={() => handleSessionClick(session.id)} className="min-w-0 flex-1 text-left">
                                <div className="truncate text-sm font-medium">{getSessionDisplayName(session)}</div>
                                <div className="text-muted-foreground text-xs">{formatSessionDate(session.updatedTime)}</div>
                            </button>
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0 opacity-0 transition-opacity group-hover:opacity-100" onClick={e => e.stopPropagation()}>
                                        <MoreHorizontal size={14} />
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-40">
                                    <DropdownMenuItem
                                        onClick={e => {
                                            e.stopPropagation();
                                            // Trigger rename - dispatch event
                                            if (typeof window !== "undefined") {
                                                window.dispatchEvent(new CustomEvent("rename-session", { detail: { session } }));
                                            }
                                        }}
                                    >
                                        <Pencil size={14} className="mr-2" />
                                        Rename
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                        onClick={e => {
                                            e.stopPropagation();
                                            // Trigger move to project
                                            if (typeof window !== "undefined") {
                                                window.dispatchEvent(new CustomEvent("move-session-to-project", { detail: { session } }));
                                            }
                                        }}
                                    >
                                        <FolderInput size={14} className="mr-2" />
                                        Move to Project
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                        onClick={e => {
                                            e.stopPropagation();
                                            handleDeleteClick(session);
                                        }}
                                    >
                                        <Trash2 size={14} className="mr-2" />
                                        Delete
                                    </DropdownMenuItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    </li>
                ))}
            </ul>

            {hasMore && (
                <Button variant="ghost" size="sm" onClick={onShowAll} className="text-muted-foreground hover:text-foreground mt-2 w-full justify-center text-xs">
                    <ChevronDown className="mr-1 size-3" />
                    Show all ({filteredSessions.length} chats)
                </Button>
            )}
        </div>
    );
};
