import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useParams, useSearchParams } from "react-router-dom";
import type { ImperativePanelHandle } from "react-resizable-panels";

import { PanelLeftIcon } from "lucide-react";

import { useChatContext, useIsNewNavigationEnabled, useTaskContext, useTurnDividerAnimation } from "@/lib/hooks";
import { SLIDE_OUT_DURATION_MS, FADE_OUT_DURATION_MS } from "@/lib/hooks/useTurnDividerAnimation";
import { ChatInputArea, ChatMessage, ChatSessionDialog, ChatSidePanel, LoadingMessageRow, SessionSidePanel } from "@/lib/components/chat";
import { Header } from "@/lib/components/header";
import { Button, ChatMessageList, CHAT_STYLES, ResizableHandle, ResizablePanel, ResizablePanelGroup, Spinner } from "@/lib/components/ui";
import { PageLayout } from "@/lib/components/layout";
import type { ChatMessageListRef } from "@/lib/components/ui/chat/chat-message-list";

const COLLAPSED_STYLE = { height: 0, overflow: "hidden" } as const;
const NO_OVERFLOW_ANCHOR_STYLE = { overflowAnchor: "none" } as const;
const OVERFLOW_ANCHOR_AUTO_STYLE = { overflowAnchor: "auto" } as const;

const COLLAPSED_SIZE = 4;
const CHAT_PANEL = { default: 50, min: 30, max: 96 };
const SIDE_PANEL = { default: 50, min: 20, max: 70 };

export function AgentChatPage() {
    const { agentName } = useParams<{ agentName: string }>();
    const [searchParams] = useSearchParams();
    const showPanel = searchParams.get("panel") === "true";
    const showHeader = searchParams.get("header") === "true";
    const useNewNav = useIsNewNavigationEnabled();

    const {
        agents,
        agentsRefetch,
        sessionId,
        messages,
        isResponding,
        isLoadingSession,
        setSelectedAgentName,
        isSidePanelCollapsed,
        setIsSidePanelCollapsed,
        turnDividerIndex,
    } = useChatContext();

    useEffect(() => {
        agentsRefetch();
    }, [agentsRefetch]);

    // Lock agent selection to the one from the URL
    useEffect(() => {
        if (agentName) {
            setSelectedAgentName(agentName);
        }
    }, [agentName, setSelectedAgentName]);

    const { isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream } = useTaskContext();

    const [isSessionSidePanelCollapsed, setIsSessionSidePanelCollapsed] = useState(true);

    const handleSessionSidePanelToggle = useCallback(() => {
        setIsSessionSidePanelCollapsed(prev => !prev);
    }, []);

    const chatMessageListRef = useRef<ChatMessageListRef>(null);
    const chatSidePanelRef = useRef<ImperativePanelHandle>(null);
    const lastExpandedSizeRef = useRef<number | null>(null);
    const [isSidePanelTransitioning, setIsSidePanelTransitioning] = useState(false);

    const { hasDivider, isHistoryCollapsed, isExitingHistory, newTurnAnchorRef, collapsedUpToIndex } = useTurnDividerAnimation({
        turnDividerIndex,
        messagesLength: messages.length,
        sessionId,
        chatMessageListRef,
    });

    const dividerIdx = hasDivider && turnDividerIndex !== null ? turnDividerIndex : 0;
    const collapseIdx = collapsedUpToIndex ?? 0;

    const prevTurnRef = useRef<HTMLDivElement>(null);
    const [prevTurnHeight, setPrevTurnHeight] = useState(0);

    useEffect(() => {
        if (isExitingHistory && prevTurnRef.current) {
            setPrevTurnHeight(prevTurnRef.current.offsetHeight);
        } else if (!isExitingHistory) {
            setPrevTurnHeight(0);
        }
    }, [isExitingHistory]);

    const lastMessageIndexByTaskId = useMemo(() => {
        const map = new Map<string, number>();
        messages.forEach((message, index) => {
            if (message.taskId) {
                map.set(message.taskId, index);
            }
        });
        return map;
    }, [messages]);

    const lockedAgents = useMemo(() => {
        if (!agentName) return agents;
        return agents.filter(a => a.name === agentName);
    }, [agents, agentName]);

    // Side panel handlers (mirrors ChatPage)
    const handleSidepanelToggle = useCallback(
        (collapsed: boolean) => {
            setIsSidePanelTransitioning(true);
            if (chatSidePanelRef.current) {
                if (collapsed) {
                    chatSidePanelRef.current.resize(COLLAPSED_SIZE);
                } else {
                    const targetSize = lastExpandedSizeRef.current || SIDE_PANEL.default;
                    chatSidePanelRef.current.resize(targetSize);
                }
            }
            setTimeout(() => setIsSidePanelTransitioning(false), 300);
        },
        []
    );

    const handleSidepanelCollapse = useCallback(() => setIsSidePanelCollapsed(true), [setIsSidePanelCollapsed]);
    const handleSidepanelExpand = useCallback(() => setIsSidePanelCollapsed(false), [setIsSidePanelCollapsed]);

    const handleSidepanelResize = useCallback((size: number) => {
        if (size > COLLAPSED_SIZE + 1) {
            lastExpandedSizeRef.current = size;
        }
    }, []);

    useEffect(() => {
        if (chatSidePanelRef.current && isSidePanelCollapsed) {
            chatSidePanelRef.current.resize(COLLAPSED_SIZE);
        }
        const handleExpandSidePanel = () => {
            if (chatSidePanelRef.current && isSidePanelCollapsed) {
                setIsSidePanelTransitioning(true);
                const targetSize = lastExpandedSizeRef.current || SIDE_PANEL.default;
                chatSidePanelRef.current.resize(targetSize);
                setIsSidePanelCollapsed(false);
                setTimeout(() => setIsSidePanelTransitioning(false), 300);
            }
        };
        window.addEventListener("expand-side-panel", handleExpandSidePanel);
        return () => window.removeEventListener("expand-side-panel", handleExpandSidePanel);
    }, [isSidePanelCollapsed, setIsSidePanelCollapsed]);

    useEffect(() => {
        const handleWindowFocus = () => {
            if (!isTaskMonitorConnected && !isTaskMonitorConnecting && taskMonitorSseError) {
                connectTaskMonitorStream();
            }
        };
        window.addEventListener("focus", handleWindowFocus);
        return () => window.removeEventListener("focus", handleWindowFocus);
    }, [isTaskMonitorConnected, isTaskMonitorConnecting, taskMonitorSseError, connectTaskMonitorStream]);

    const chatContent = isLoadingSession ? (
        <div className="flex h-full items-center justify-center">
            <Spinner size="medium" variant="primary">
                <p className="mt-4 text-sm text-(--secondary-text-wMain)">Loading session...</p>
            </Spinner>
        </div>
    ) : (
        <>
            <ChatMessageList className="text-base" ref={chatMessageListRef}>
                {hasDivider && (
                    <div style={isHistoryCollapsed ? COLLAPSED_STYLE : undefined}>
                        {messages.slice(0, collapseIdx).map((message, index) => {
                            const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                            const messageKey = message.metadata?.messageId || `temp-${index}`;
                            return (
                                <div key={messageKey} style={NO_OVERFLOW_ANCHOR_STYLE}>
                                    <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} isStreaming={false} />
                                </div>
                            );
                        })}
                    </div>
                )}
                {hasDivider && collapseIdx < dividerIdx && (
                    <div
                        ref={prevTurnRef}
                        style={{
                            marginTop: isExitingHistory && prevTurnHeight > 0 ? `-${prevTurnHeight}px` : 0,
                            opacity: isExitingHistory ? 0 : 1,
                            transition: isExitingHistory
                                ? `margin-top ${SLIDE_OUT_DURATION_MS}ms ease-out, opacity ${FADE_OUT_DURATION_MS}ms ease-in`
                                : undefined,
                            overflow: "hidden",
                        }}
                    >
                        {messages.slice(collapseIdx, dividerIdx).map((message, i) => {
                            const index = i + collapseIdx;
                            const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                            const messageKey = message.metadata?.messageId || `temp-${index}`;
                            return (
                                <div key={messageKey}>
                                    <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} isStreaming={false} />
                                </div>
                            );
                        })}
                    </div>
                )}
                {(hasDivider ? messages.slice(dividerIdx) : messages).map((message, i) => {
                    const index = hasDivider ? i + dividerIdx : i;
                    const isLastWithTaskId = !!(message.taskId && lastMessageIndexByTaskId.get(message.taskId) === index);
                    const messageKey = message.metadata?.messageId || `temp-${index}`;
                    const isLastMessage = index === messages.length - 1;
                    const shouldStream = isLastMessage && isResponding && !message.isUser;
                    const isNewTurnStart = hasDivider && i === 0;

                    return (
                        <div key={messageKey} ref={isNewTurnStart ? newTurnAnchorRef : undefined} style={isNewTurnStart ? OVERFLOW_ANCHOR_AUTO_STYLE : undefined}>
                            <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} isStreaming={shouldStream} />
                        </div>
                    );
                })}
                {isResponding && <LoadingMessageRow />}
            </ChatMessageList>
            <div style={CHAT_STYLES}>
                <ChatInputArea agents={lockedAgents} scrollToBottom={chatMessageListRef.current?.scrollToBottom} hideAgentSelector />
            </div>
        </>
    );

    return (
        <PageLayout className="relative">
            {showHeader && !useNewNav && (
                <div
                    inert={isSessionSidePanelCollapsed}
                    className={`absolute top-0 left-0 z-20 h-screen transition-[transform,visibility] duration-300 ${isSessionSidePanelCollapsed ? "invisible -translate-x-full delay-300" : "visible translate-x-0"}`}
                >
                    <SessionSidePanel onToggle={handleSessionSidePanelToggle} />
                </div>
            )}
            {showHeader && (
                <div className={`transition-all duration-300 ${!useNewNav && !isSessionSidePanelCollapsed ? "ml-100" : "ml-0"}`}>
                    <Header
                        title={agentName ?? ""}
                        leadingAction={
                            useNewNav ? (
                                <ChatSessionDialog />
                            ) : isSessionSidePanelCollapsed ? (
                                <div className="flex items-center gap-2">
                                    <Button variant="ghost" onClick={handleSessionSidePanelToggle} className="h-10 w-10 p-0" tooltip="Show Chat Sessions">
                                        <PanelLeftIcon className="size-5" />
                                    </Button>
                                    <div className="h-6 border-r"></div>
                                    <ChatSessionDialog />
                                </div>
                            ) : null
                        }
                    />
                </div>
            )}
            <div className={`flex min-h-0 flex-1 transition-all duration-300 ${showHeader && !useNewNav && !isSessionSidePanelCollapsed ? "ml-100" : "ml-0"}`}>
                {showPanel ? (
                    <ResizablePanelGroup direction="horizontal" autoSaveId="agent-chat-side-panel" className="h-full">
                        <ResizablePanel defaultSize={CHAT_PANEL.default} minSize={CHAT_PANEL.min} maxSize={CHAT_PANEL.max} id="agent-chat-panel">
                            <div className="flex h-full w-full flex-col">
                                <div className="flex min-h-0 flex-1 flex-col py-6">
                                    {chatContent}
                                </div>
                            </div>
                        </ResizablePanel>
                        <ResizableHandle />
                        <ResizablePanel
                            ref={chatSidePanelRef}
                            defaultSize={SIDE_PANEL.default}
                            minSize={SIDE_PANEL.min}
                            maxSize={SIDE_PANEL.max}
                            collapsedSize={COLLAPSED_SIZE}
                            collapsible
                            onCollapse={handleSidepanelCollapse}
                            onExpand={handleSidepanelExpand}
                            onResize={handleSidepanelResize}
                            id="agent-chat-side-panel"
                            className={isSidePanelTransitioning ? "transition-all duration-300 ease-in-out" : ""}
                        >
                            <div className="h-full">
                                <ChatSidePanel
                                    onCollapsedToggle={handleSidepanelToggle}
                                    isSidePanelCollapsed={isSidePanelCollapsed}
                                    setIsSidePanelCollapsed={setIsSidePanelCollapsed}
                                />
                            </div>
                        </ResizablePanel>
                    </ResizablePanelGroup>
                ) : (
                    <div className="flex min-h-0 flex-1 flex-col py-6">
                        {chatContent}
                    </div>
                )}
            </div>
        </PageLayout>
    );
}
