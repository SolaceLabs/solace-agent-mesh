import { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { cva } from "class-variance-authority";
import { MessageCircle, CalendarDays, Share2 } from "lucide-react";

import { useMarkSessionViewed, useRecentSessions } from "@/lib/api/sessions";
import { useSharedWithMe } from "@/lib/api/share";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";
import { useChatContext, useConfigContext, useIsAutoTitleGenerationEnabled, useIsChatSharingEnabled, useTitleAnimation } from "@/lib/hooks";
import { Spinner, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import type { Session } from "@/lib/types";
import type { SharedWithMeItem } from "@/lib/types/share";
import { hasUnseenUpdates, toEpochMs } from "@/lib/utils";

const sessionButtonStyles = cva(["relative", "flex", "h-10", "w-full", "cursor-pointer", "items-center", "gap-2", "pr-4", "pl-6", "text-left", "transition-colors", "hover:bg-(--darkSurface-bgHover)"], {
    variants: {
        active: {
            true: "bg-(--darkSurface-bgActive)",
            false: "",
        },
    },
    defaultVariants: { active: false },
});

const sessionTextStyles = cva(["block", "truncate", "text-sm", "transition-opacity", "duration-300"], {
    variants: {
        active: {
            true: "font-bold text-(--darkSurface-text)",
            false: "text-(--darkSurface-textMuted)",
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

function SessionName({ session, respondingSessionId, isActive, hasRunningBackgroundTask }: SessionNameProps) {
    const autoTitleGenerationEnabled = useIsAutoTitleGenerationEnabled();

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
}

interface RecentChatsListProps {
    maxItems?: number;
}

type SessionEntry = { kind: "session"; timestamp: number; session: Session };
type SharedEntry = { kind: "shared"; timestamp: number; shared: SharedWithMeItem };
type Entry = SessionEntry | SharedEntry;

export function RecentChatsList({ maxItems = MAX_RECENT_CHATS }: RecentChatsListProps) {
    const navigate = useNavigate();
    const { sessionId, handleSwitchSession, currentTaskId } = useChatContext();
    const { persistenceEnabled } = useConfigContext();
    const chatSharingEnabled = useIsChatSharingEnabled();

    const { data: sessionsData, isLoading, isFetching } = useRecentSessions(maxItems);
    const sessions = useMemo(() => sessionsData ?? [], [sessionsData]);
    const { data: sharedItems = [] } = useSharedWithMe();
    const markViewedMutation = useMarkSessionViewed();

    // Mark the active session as viewed whenever it's selected or its updatedTime advances.
    // SSE can bump `updated_time` per streamed chunk (~1s), so gate with a ref to only
    // fire when the viewed timestamp is actually behind the latest update we've acted on.
    const lastMarkedViewedRef = useRef<Map<string, number>>(new Map());
    useEffect(() => {
        if (!sessionId) return;
        const active = sessions.find(s => s.id === sessionId);
        if (!active) return;
        if (!hasUnseenUpdates(active)) return;
        const updatedMs = toEpochMs(active.updatedTime);
        if (!Number.isFinite(updatedMs)) return;
        const lastMarked = lastMarkedViewedRef.current.get(active.id) ?? 0;
        if (lastMarked >= updatedMs) return;
        lastMarkedViewedRef.current.set(active.id, updatedMs);
        markViewedMutation.mutate(active.id);
        // Only depend on id + updatedTime to avoid re-firing on unrelated re-renders.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, sessions.find(s => s.id === sessionId)?.updatedTime]);

    const prevSessionRef = useRef<string | null>(sessionId);
    useEffect(() => {
        const prev = prevSessionRef.current;
        if (prev && prev !== sessionId) {
            markViewedMutation.mutate(prev);
        }
        prevSessionRef.current = sessionId;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

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

    const entries = useMemo<Entry[]>(() => {
        const sessionEntries: Entry[] = sessions.map(session => ({
            kind: "session",
            timestamp: new Date(session.updatedTime).getTime() || 0,
            session,
        }));

        const sharedEntries: Entry[] = chatSharingEnabled ? sharedItems.map(shared => ({ kind: "shared", timestamp: shared.sharedAt || 0, shared })) : [];

        return [...sessionEntries, ...sharedEntries].sort((a, b) => b.timestamp - a.timestamp).slice(0, maxItems);
    }, [sessions, sharedItems, chatSharingEnabled, maxItems]);

    const handleSessionClick = async (clickedSession: Session) => {
        // Navigate to chat page first, then switch session
        navigate("/chat");
        await handleSwitchSession(clickedSession.id);
        // Mark viewed AFTER switch completes — switching can trigger SSE
        // replay / save_task calls that advance the session's updated_time
        // by a few ms, so writing last_viewed_at first would leave us behind.
        markViewedMutation.mutate(clickedSession.id);
    };

    const handleSharedClick = async (item: SharedWithMeItem) => {
        const isEditor = item.accessLevel === "RESOURCE_EDITOR" && item.sessionId;
        if (isEditor && item.sessionId) {
            navigate("/chat");
            await handleSwitchSession(item.sessionId);
        } else {
            navigate(`/shared-chat/${item.shareId}`);
        }
    };

    // Show the spinner whenever the recent-sessions query has no resolved data
    // for the current user yet — covers initial load and the brief window
    // after a user-scoped cache key changes (e.g. user switch). Prevents any
    // chance of rendering another user's stale list before the fetch settles.
    const recentNotReady = sessionsData === undefined && isFetching;
    if ((isLoading || recentNotReady) && entries.length === 0 && persistenceEnabled) {
        return (
            <div className="flex h-full flex-col items-center pt-[25%] text-xs text-(--secondary-text-wMain)">
                <Spinner />
            </div>
        );
    }

    if (entries.length === 0) {
        return (
            <div className="flex h-full flex-col items-center pt-[25%] text-xs text-(--secondary-text-wMain)">
                <MessageCircle className="mb-2 h-6 w-6" />
                No recent chats
            </div>
        );
    }

    return (
        <div className="flex flex-col">
            {entries.map(entry => {
                if (entry.kind === "session") {
                    const { session } = entry;
                    const displayName = session.name?.trim() || "New Chat";
                    const isActive = session.id === sessionId;
                    const hasUnseen = !isActive && hasUnseenUpdates(session);
                    return (
                        <Tooltip key={`session-${session.id}`}>
                            <TooltipTrigger asChild>
                                <button onClick={() => handleSessionClick(session)} className={sessionButtonStyles({ active: isActive })}>
                                    {hasUnseen && <span aria-label="Unseen updates" className="absolute top-1/2 left-[10px] h-[42px] w-1 -translate-y-1/2 rounded-sm bg-(--info-wMain)" />}
                                    {session.source === "scheduler" ? <CalendarDays className="h-4 w-4 flex-shrink-0 text-(--darkSurface-textMuted)" /> : <MessageCircle className="h-4 w-4 flex-shrink-0 text-(--darkSurface-textMuted)" />}
                                    <div className="min-w-0 flex-1">
                                        <SessionName session={session} respondingSessionId={respondingSessionId} isActive={isActive} hasRunningBackgroundTask={session.hasRunningBackgroundTask} />
                                    </div>
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="top">{displayName}</TooltipContent>
                        </Tooltip>
                    );
                }

                const { shared } = entry;
                return (
                    <Tooltip key={`shared-${shared.shareId}`}>
                        <TooltipTrigger asChild>
                            <button onClick={() => handleSharedClick(shared)} className={sessionButtonStyles({ active: false })}>
                                <Share2 className="h-4 w-4 flex-shrink-0 text-(--darkSurface-textMuted)" aria-label="Shared with me" />
                                <div className="min-w-0 flex-1">
                                    <span className={sessionTextStyles({ active: false, animation: "none" })}>{shared.title}</span>
                                </div>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                            Shared by {shared.ownerEmail}: {shared.title}
                        </TooltipContent>
                    </Tooltip>
                );
            })}
        </div>
    );
}
