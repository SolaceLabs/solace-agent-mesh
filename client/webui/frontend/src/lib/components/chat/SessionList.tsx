import React, { useEffect, useState, useRef } from "react";
import { useChatContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import { useConfigContext } from "@/lib/hooks";
import { useAuthContext } from "@/lib/hooks";
import { Edit, Trash2, Check, X } from "lucide-react";

interface Session {
    id: string;
    created_at: string;
    updated_at: string;
    name: string | null;
}

export const SessionList: React.FC = () => {
    const { handleSwitchSession, updateSessionName, openSessionDeleteModal } = useChatContext();
    const { configServerUrl } = useConfigContext();
    useAuthContext();
    const apiPrefix = `${configServerUrl}/api/v1`;
    const [sessions, setSessions] = useState<Session[]>([]);
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const inputRef = useRef<HTMLInputElement>(null);

    const fetchSessions = async () => {
        const url = `${apiPrefix}/sessions`;
        try {
            const response = await authenticatedFetch(url);
            if (response.ok) {
                const data = await response.json();
                setSessions(data.sessions || []);
            } else {
                console.error(`Failed to fetch sessions: ${response.status} ${response.statusText}`);
            }
        } catch (error) {
            console.error("An error occurred while fetching sessions:", error);
        }
    };

    useEffect(() => {
        fetchSessions();
        const handleNewSession = () => {
            fetchSessions();
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
    }, [apiPrefix]);

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
        return new Date(dateString).toLocaleString();
    };

    const getSessionDisplayName = (session: Session) => {
        if (session.name && session.name.trim()) {
            return session.name;
        }
        // Generate a short, readable identifier from the session ID  
        const sessionId = session.id;
        if (sessionId.startsWith('web-session-')) {
            // Extract the UUID part and create a short identifier
            const uuid = sessionId.replace('web-session-', '');
            const shortId = uuid.substring(0, 8);
            return `Chat ${shortId}`;
        }
        // Fallback for other ID formats
        return `Session ${sessionId.substring(0, 8)}`;
    };

    return (
        <div className="p-4">
            <h2 className="text-lg font-bold mb-4">Chat History</h2>
            <ul>
                {sessions.map((session) => (
                    <li key={session.id} className="mb-2 group">
                        <div className="flex items-center justify-between p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700">
                            {editingSessionId === session.id ? (
                                <input
                                    ref={inputRef}
                                    type="text"
                                    value={editingSessionName}
                                    onChange={(e) => setEditingSessionName(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                                    onBlur={handleRename}
                                    className="flex-grow bg-transparent focus:outline-none"
                                />
                            ) : (
                                <button onClick={() => handleSessionClick(session.id)} className="flex-grow text-left">
                                    <div className="flex flex-col">
                                        <span className="font-semibold">{getSessionDisplayName(session)}</span>
                                        <span className="text-xs text-gray-500">{formatSessionDate(session.updated_at)}</span>
                                    </div>
                                </button>
                            )}
                            <div className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                                {editingSessionId === session.id ? (
                                    <>
                                        <button onClick={handleRename} className="p-1 hover:bg-gray-300 dark:hover:bg-gray-700 rounded"><Check size={16} /></button>
                                        <button onClick={() => setEditingSessionId(null)} className="p-1 hover:bg-gray-300 dark:hover:bg-gray-700 rounded"><X size={16} /></button>
                                    </>
                                ) : (
                                    <>
                                        <button onClick={() => handleEditClick(session)} className="p-1 hover:bg-gray-300 dark:hover:bg-gray-700 rounded"><Edit size={16} /></button>
                                        <button onClick={() => handleDeleteClick(session)} className="p-1 hover:bg-gray-300 dark:hover:bg-gray-700 rounded"><Trash2 size={16} /></button>
                                    </>
                                )}
                            </div>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
};