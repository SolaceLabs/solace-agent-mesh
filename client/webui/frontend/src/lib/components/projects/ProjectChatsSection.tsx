import React from "react";
import { MessageCircle, Calendar } from "lucide-react";

import { useProjectSessions } from "@/lib/hooks/useProjectSessions";
import { Spinner } from "@/lib/components/ui/spinner";
import { formatTimestamp } from "@/lib/utils/format";
import type { Project } from "@/lib/types/projects";

interface ProjectChatsSectionProps {
    project: Project;
    onChatClick: (sessionId: string) => void;
}

export const ProjectChatsSection: React.FC<ProjectChatsSectionProps> = ({
    project,
    onChatClick,
}) => {
    const { sessions, isLoading, error } = useProjectSessions(project.id);

    return (
        <div className="px-6 py-4">
            <h3 className="text-sm font-semibold text-foreground mb-3">Chats</h3>
            
            {isLoading && (
                <div className="flex items-center justify-center p-8">
                    <Spinner size="small" />
                </div>
            )}

            {error && (
                <div className="text-sm text-destructive p-4 border border-destructive/50 rounded-md">
                    Error loading chats: {error}
                </div>
            )}

            {!isLoading && !error && sessions.length === 0 && (
                <div className="flex flex-col items-center justify-center p-8 text-center border border-dashed rounded-md">
                    <MessageCircle className="h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                        No chats yet. Activate this project to start chatting.
                    </p>
                </div>
            )}

            {!isLoading && !error && sessions.length > 0 && (
                <div className="space-y-2">
                    {sessions.map((session) => (
                        <div
                            key={session.id}
                            className="p-3 border rounded-md hover:bg-accent/50 cursor-pointer transition-colors"
                            onClick={() => onChatClick(session.id)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" || e.key === " ") {
                                    e.preventDefault();
                                    onChatClick(session.id);
                                }
                            }}
                        >
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-foreground truncate">
                                        {session.name || `Chat ${session.id.substring(0, 8)}`}
                                    </p>
                                    <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
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
