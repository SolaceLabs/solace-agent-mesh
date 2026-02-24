import React, { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircle, Loader2 } from "lucide-react";

import { useRecentSessions } from "@/lib/api/sessions";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { useChatContext, useConfigContext, useTitleAnimation } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { Session } from "@/lib/types";

interface SessionNameProps {
    session: Session;
    respondingSessionId: string | null;
    isActive: boolean;
}

const SessionName: React.FC<SessionNameProps> = ({ session, respondingSessionId, isActive }) => {
    const { autoTitleGenerationEnabled } = useConfigContext();

    const displayName = useMemo(() => {
        if (session.name && session.name.trim()) {
            return session.name;
        }
        return "New Chat";
    }, [session.name]);

    const { text: animatedName, isAnimating, isGenerating } = useTitleAnimation(displayName, session.id);

    const isWaitingForTitle = useMemo(() => {
        if (isGenerating) {
            return true;
        }

        if (!autoTitleGenerationEnabled) {
            return false;
        }
        const isNewChat = !session.name || session.name === "New Chat";
        const isThisSessionResponding = respondingSessionId === session.id;
        return isThisSessionResponding && isNewChat;
    }, [session.name, session.id, respondingSessionId, isGenerating, autoTitleGenerationEnabled]);

    const animationClass = useMemo(() => {
        if (isGenerating || isAnimating) {
            if (isWaitingForTitle) {
                return "animate-pulse-slow";
            }
            return "animate-pulse opacity-50";
        }
        if (isWaitingForTitle) {
            return "animate-pulse-slow";
        }
        return "opacity-100";
    }, [isWaitingForTitle, isAnimating, isGenerating]);

    return <span className={cn("truncate text-sm transition-opacity duration-300", animationClass, isActive ? "text-[var(--color-primary-text-w10)]" : "text-[var(--color-secondary-text-w50)]")}>{animatedName}</span>;
};

interface RecentChatsListProps {
    maxItems?: number;
}

export const RecentChatsList: React.FC<RecentChatsListProps> = ({ maxItems = MAX_RECENT_CHATS }) => {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, currentTaskId } = useChatContext();
    const { persistenceEnabled } = useConfigContext();

    // Fetch recent sessions using React Query
    const { data: sessions = [], isLoading } = useRecentSessions(maxItems);

    // Track which session started the response
    const taskToSessionRef = useRef<Map<string, string>>(new Map());
    const [taskMapVersion, setTaskMapVersion] = useState(0);

    useEffect(() => {
        if (currentTaskId && !taskToSessionRef.current.has(currentTaskId)) {
            taskToSessionRef.current.set(currentTaskId, sessionId);
            setTaskMapVersion(v => v + 1);
        }
    }, [currentTaskId, sessionId]);

    const respondingSessionId = useMemo(() => {
        if (!currentTaskId) return null;
        return taskToSessionRef.current.get(currentTaskId) || null;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentTaskId, taskMapVersion]);

    const handleSessionClick = async (clickedSessionId: string) => {
        // Navigate to chat page first, then switch session
        navigate("/chat");
        await handleSwitchSession(clickedSessionId);
    };

    if (!persistenceEnabled) {
        return <div className="text-muted-foreground py-2 text-center text-xs">Persistence is not enabled.</div>;
    }

    if (isLoading && sessions.length === 0) {
        return (
            <div className="flex items-center justify-center py-4">
                <Loader2 className="text-muted-foreground h-4 w-4 animate-spin" />
            </div>
        );
    }

    if (sessions.length === 0) {
        return (
            <div className="text-muted-foreground flex flex-col items-center justify-center py-4 text-xs">
                <MessageCircle className="mb-2 h-6 w-6" />
                No recent chats
            </div>
        );
    }

    return (
        <div className="flex flex-col">
            {sessions.slice(0, maxItems).map(session => (
                <button
                    key={session.id}
                    onClick={() => handleSessionClick(session.id)}
                    className={cn("flex h-10 w-full items-center gap-2 rounded pr-4 pl-6 text-left transition-colors hover:bg-[var(--color-background-w100)]", session.id === sessionId && "bg-[var(--color-background-w100)]")}
                >
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                            <SessionName session={session} respondingSessionId={respondingSessionId} isActive={session.id === sessionId} />
                            {session.hasRunningBackgroundTask && (
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Loader2 className="text-primary h-3 w-3 flex-shrink-0 animate-spin" />
                                    </TooltipTrigger>
                                    <TooltipContent>Background task running</TooltipContent>
                                </Tooltip>
                            )}
                        </div>
                    </div>
                </button>
            ))}
        </div>
    );
};
