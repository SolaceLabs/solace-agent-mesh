import React from "react";
import { MessageCircle, Calendar, Plus } from "lucide-react";

import { useProjectSessions } from "@/lib/api/projects/hooks";
import { Spinner } from "@/lib/components/ui/spinner";
import { Button } from "@/lib/components/ui";
import { formatTimestamp } from "@/lib/utils/format";
import type { Project } from "@/lib/types/projects";

interface ProjectChatsSectionProps {
    project: Project;
    onChatClick: (sessionId: string) => void;
    onStartNewChat?: () => void;
}

export const ProjectChatsSection: React.FC<ProjectChatsSectionProps> = ({ project, onChatClick, onStartNewChat }) => {
    const { data: sessions = [], isLoading, error } = useProjectSessions(project.id);

    return (
        <div className="px-6 py-4">
            <div className="mb-3 flex items-center justify-between">
                <h3 className="text-foreground text-sm font-semibold">Chats</h3>
                {onStartNewChat && (
                    <Button onClick={onStartNewChat} size="sm" testid="startNewChatButton">
                        <Plus className="mr-2 h-4 w-4" />
                        New Chat
                    </Button>
                )}
            </div>

            {isLoading && (
                <div className="flex items-center justify-center p-8">
                    <Spinner size="small" />
                </div>
            )}

            {error && <div className="text-destructive border-destructive/50 rounded-md border p-4 text-sm">Error loading chats: {error.message}</div>}

            {!isLoading && !error && sessions.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-md border border-dashed p-8 text-center">
                    <MessageCircle className="text-muted-foreground mb-2 h-8 w-8" />
                    <p className="text-muted-foreground mb-4 text-sm">No chats. Start a chat with all the knowledge and context from this project.</p>
                    {onStartNewChat && (
                        <Button onClick={onStartNewChat} size="sm" testid="startNewChatButtonNoChats">
                            <Plus className="mr-2 h-4 w-4" />
                            Start New Chat
                        </Button>
                    )}
                </div>
            )}

            {!isLoading && !error && sessions.length > 0 && (
                <div className="space-y-2">
                    {sessions.map(session => (
                        <div
                            key={session.id}
                            className="hover:bg-accent/50 cursor-pointer rounded-md border p-3 shadow-sm transition-colors"
                            onClick={() => onChatClick(session.id)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={e => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    onChatClick(session.id);
                                }
                            }}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                    <p className="text-foreground truncate text-sm font-medium">{session.name || `Chat ${session.id.substring(0, 8)}`}</p>
                                    <div className="text-muted-foreground mt-1 flex items-center gap-1 text-xs">
                                        <Calendar className="h-3 w-3" />
                                        <span>{formatTimestamp(session.updatedTime)}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
