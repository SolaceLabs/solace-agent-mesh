import React, { useEffect, useState, useRef } from "react";
import { useChatContext } from "@/lib/hooks";
import { Edit, Trash2, Check, X } from "lucide-react";
import type { Session } from "@/lib/types";

export const SessionList: React.FC = () => {
    const { sessions, handleSwitchSession, updateSessionName, openSessionDeleteModal } = useChatContext();
    const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
    const [editingSessionName, setEditingSessionName] = useState<string>("");
    const inputRef = useRef<HTMLInputElement>(null);

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
