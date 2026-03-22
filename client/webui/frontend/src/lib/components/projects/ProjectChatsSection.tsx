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
    isDisabled?: boolean;
}

export const ProjectChatsSection = ({ project, onChatClick, onStartNewChat, isDisabled = false }: ProjectChatsSectionProps) => {
    const { data: sessions = [], isLoading, error } = useProjectSessions(project.id);

    return (
        <div className="px-6 py-4">
            <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-(--primary-text-wMain)">Chats</h3>
                {onStartNewChat && (
                    <Button onClick={onStartNewChat} size="sm" testid="startNewChatButton" disabled={isDisabled}>
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

            {error && <div className="rounded-md border border-(--error-wMain) p-4 text-sm text-(--error-wMain)">Error loading chats: {error.message}</div>}

            {!isLoading && !error && sessions.length === 0 && (
                <div className="flex flex-col items-center justify-center rounded-md border border-dashed p-8 text-center">
                    <MessageCircle className="mb-2 h-8 w-8 text-(--secondary-text-wMain)" />
                    <p className="mb-4 text-sm text-(--secondary-text-wMain)">No chats. Start a chat with all the knowledge and context from this project.</p>
                    {onStartNewChat && (
                        <Button onClick={onStartNewChat} size="sm" testid="startNewChatButtonNoChats" disabled={isDisabled}>
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
                            className="cursor-pointer rounded-md border p-3 shadow-sm transition-colors hover:bg-(--secondary-w20)"
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
                                    <p className="truncate text-sm font-medium text-(--primary-text-wMain)">{session.name || `Chat ${session.id.substring(0, 8)}`}</p>
                                    <div className="mt-1 flex items-center gap-1 text-xs text-(--secondary-text-wMain)">
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
