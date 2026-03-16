import React, { useMemo, useRef } from "react";

import { useChatContext } from "@/lib/hooks";
import type { AgentWelcomeConfig, MessageFE, TextPart } from "@/lib/types";
import { ChatMessageList, CHAT_STYLES, Spinner } from "@/lib/components/ui";
import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

import { ChatInputArea } from "./ChatInputArea";
import { ChatMessage } from "./ChatMessage";
import { ChatWelcomeScreen } from "./ChatWelcomeScreen";
import { LoadingMessageRow } from "./LoadingMessageRow";

export interface ChatAreaProps {
    /** Compact layout for floating panels — reduces spacing */
    compact?: boolean;
    /** When true, never shows the welcome screen (always show input area) */
    hideWelcomeScreen?: boolean;
    /** Optional className for the outermost wrapper div */
    className?: string;
    /**
     * Callback for "View Progress" click on the loading row.
     * - undefined (default): uses default behavior (open side panel activity tab)
     * - null: hides the view progress button entirely
     * - function: custom callback
     */
    onViewProgress?: (() => void) | null;
    /** Fallback welcome config used when the selected agent's card hasn't been discovered yet. */
    welcomeOverride?: AgentWelcomeConfig;
    /** Optional callback to render extra content after each chat message (e.g. action buttons). */
    renderMessageAddon?: (message: MessageFE, index: number) => React.ReactNode;
}

/**
 * Reusable chat area component containing the message list, input area, and loading state.
 * Pulls all data from ChatContext — no prop drilling required.
 *
 * Used by ChatPage (full-size) and FloatingChatPanel (compact mode).
 */
export const ChatArea: React.FC<ChatAreaProps> = ({ compact = false, hideWelcomeScreen = false, className, onViewProgress, welcomeOverride, renderMessageAddon }) => {
    const chatMessageListRef = useRef<ChatMessageListRef>(null);
    const {
        messages,
        agents,
        isResponding,
        isLoadingSession,
        latestStatusText,
        currentTaskId,
        selectedAgentName,
        setTaskIdInSidePanel,
        openSidePanelTab,
    } = useChatContext();

    const lastMessageIndexByTaskId = useMemo(() => {
        const map = new Map<string, number>();
        messages.forEach((message, index) => {
            if (message.taskId) {
                map.set(message.taskId, index);
            }
        });
        return map;
    }, [messages]);

    const isWelcomeState = useMemo(() => {
        if (messages.length === 0) return true;
        if (messages.length === 1 && !messages[0].isUser && messages[0].metadata?.sessionId === "") return true;
        return false;
    }, [messages]);

    const loadingMessage = useMemo(() => {
        return messages.find(message => message.isStatusBubble);
    }, [messages]);

    const backendStatusText = useMemo(() => {
        if (!loadingMessage || !loadingMessage.parts) return null;
        const textPart = loadingMessage.parts.find(p => p.kind === "text") as TextPart | undefined;
        return textPart?.text || null;
    }, [loadingMessage]);

    const resolvedOnViewProgress = useMemo(() => {
        if (onViewProgress === null) return undefined;
        if (onViewProgress !== undefined) return onViewProgress;
        // Default: open side panel activity tab
        if (!currentTaskId) return undefined;
        return () => {
            setTaskIdInSidePanel(currentTaskId);
            openSidePanelTab("activity");
        };
    }, [onViewProgress, currentTaskId, setTaskIdInSidePanel, openSidePanelTab]);

    const showWelcome = !hideWelcomeScreen && isWelcomeState && !isResponding;
    const paddingClass = compact ? "py-2" : "py-6";
    const textSizeClass = compact ? "text-sm" : "text-base";

    return (
        <div className={`flex h-full w-full flex-col ${className ?? ""}`}>
            <div className={`flex min-h-0 flex-1 flex-col ${paddingClass}`}>
                {isLoadingSession ? (
                    <div className="flex h-full items-center justify-center">
                        <Spinner size="medium" variant="primary">
                            <p className="text-muted-foreground mt-4 text-sm">Loading session...</p>
                        </Spinner>
                    </div>
                ) : showWelcome ? (
                    <ChatWelcomeScreen agents={agents} selectedAgentName={selectedAgentName} welcomeOverride={welcomeOverride} compact={compact} />
                ) : (
                    <>
                        <ChatMessageList className={textSizeClass} ref={chatMessageListRef}>
                            {messages.map((message, index) => {
                                const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                                const messageKey = message.metadata?.messageId || `temp-${index}`;
                                const isLastMessage = index === messages.length - 1;
                                const shouldStream = isLastMessage && isResponding && !message.isUser;
                                return (
                                    <React.Fragment key={messageKey}>
                                        <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} isStreaming={shouldStream} />
                                        {renderMessageAddon?.(message, index)}
                                    </React.Fragment>
                                );
                            })}
                        </ChatMessageList>
                        <div style={CHAT_STYLES}>
                            {isResponding && <LoadingMessageRow statusText={(backendStatusText || latestStatusText.current) ?? undefined} onViewWorkflow={resolvedOnViewProgress} />}
                            <ChatInputArea agents={agents} scrollToBottom={chatMessageListRef.current?.scrollToBottom} compact={compact} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};
