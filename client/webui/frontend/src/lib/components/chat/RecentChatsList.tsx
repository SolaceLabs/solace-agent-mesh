import React, { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { cva } from "class-variance-authority";
import { MessageCircle } from "lucide-react";

import { useRecentSessions } from "@/lib/api/sessions";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { useChatContext, useConfigContext, useTitleAnimation } from "@/lib/hooks";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { Session } from "@/lib/types";

const sessionButtonStyles = cva(["flex", "h-10", "w-full", "cursor-pointer", "items-center", "gap-2", "pr-4", "pl-6", "text-left", "transition-colors", "hover:bg-[var(--color-background-w100)]"], {
    variants: {
        active: {
            true: "bg-[var(--color-background-w100)]",
            false: "",
        },
    },
    defaultVariants: { active: false },
});

const sessionTextStyles = cva(["block", "truncate", "text-sm", "transition-opacity", "duration-300"], {
    variants: {
        active: {
            true: "text-[var(--color-primary-text-w10)]",
            false: "text-[var(--color-secondary-text-w50)]",
        },
        animation: {
            pulseGenerate: "animate-pulse-slow",
            pulseWait: "animate-pulse opacity-50",
            none: "opacity-100",
        },
    },
    defaultVariants: { active: false, animation: "none" },
});

interface SessionNameProps {
    session: Session;
    respondingSessionId: string | null;
    isActive: boolean;
    hasRunningBackgroundTask?: boolean;
}

const SessionName: React.FC<SessionNameProps> = ({ session, respondingSessionId, isActive, hasRunningBackgroundTask }) => {
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

    const animationVariant = useMemo((): "pulseGenerate" | "pulseWait" | "none" => {
        if (hasRunningBackgroundTask) {
            return "pulseGenerate";
        }
        if (isGenerating || isAnimating) {
            return isWaitingForTitle ? "pulseGenerate" : "pulseWait";
        }
        if (isWaitingForTitle) {
            return "pulseGenerate";
        }
        return "none";
    }, [isWaitingForTitle, isAnimating, isGenerating, hasRunningBackgroundTask]);

    return <span className={sessionTextStyles({ active: isActive, animation: animationVariant })}>{animatedName}</span>;
};

interface RecentChatsListProps {
    maxItems?: number;
}

export const RecentChatsList: React.FC<RecentChatsListProps> = ({ maxItems = MAX_RECENT_CHATS }) => {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, currentTaskId } = useChatContext();
    const { persistenceEnabled } = useConfigContext();

    const { data: sessions = [], isLoading } = useRecentSessions(maxItems);

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
            <div className="flex flex-col py-2">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="flex h-10 items-center pl-6">
                        <span className="animate-pulse-slow text-sm text-[var(--color-secondary-text-w50)]">Loading...</span>
                    </div>
                ))}
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
            {sessions.slice(0, maxItems).map(session => {
                const displayName = session.name?.trim() || "New Chat";
                return (
                    <Tooltip key={session.id}>
                        <TooltipTrigger asChild>
                            <button onClick={() => handleSessionClick(session.id)} className={sessionButtonStyles({ active: session.id === sessionId })}>
                                <div className="min-w-0 flex-1">
                                    <SessionName session={session} respondingSessionId={respondingSessionId} isActive={session.id === sessionId} hasRunningBackgroundTask={session.hasRunningBackgroundTask} />
                                </div>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="top">{displayName}</TooltipContent>
                    </Tooltip>
                );
            })}
        </div>
    );
};
