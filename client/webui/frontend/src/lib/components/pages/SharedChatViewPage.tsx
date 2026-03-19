/**
 * SharedChatViewPage - In-app view of a shared chat session (inside AppLayout)
 *
 * Unlike SharedSessionPage (standalone, outside AppLayout), this component renders
 * inside the main app layout with sidebar and navigation visible. It provides a
 * read-only view of a shared chat with the option to fork or navigate to the
 * original chat (if owner).
 *
 * Uses the full ChatMessage component for pixel-perfect rendering parity with ChatPage.
 */

import type { ReactNode } from "react";
import { AlertCircle, Info, Loader2, MessageSquare, UserLock } from "lucide-react";
import { Button, Spinner, ResizablePanelGroup, ResizablePanel, ResizableHandle, Tooltip, TooltipContent, TooltipTrigger, CHAT_STYLES } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { ChatMessage } from "@/lib/components/chat";
import { SharedChatProvider } from "@/lib/providers/SharedChatProvider";
import { SharedSidePanel } from "@/lib/components/share/SharedSidePanel";
import { useSharedSession, formatDateYMD } from "@/lib/hooks/useSharedSession";

export function SharedChatViewPage() {
    const shared = useSharedSession();

    // Loading state
    if (shared.loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Spinner size="large" variant="primary">
                    <p className="text-muted-foreground mt-4 text-sm">Loading shared chat...</p>
                </Spinner>
            </div>
        );
    }

    // Error state
    if (shared.error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-destructive h-16 w-16" />
                <h1 className="text-2xl font-semibold">Unable to View Shared Chat</h1>
                <p className="text-muted-foreground max-w-md text-center">{shared.error}</p>
                <Button variant="outline" onClick={() => shared.navigate("/chat")}>
                    Go to Chat
                </Button>
            </div>
        );
    }

    // Not found state
    if (!shared.session) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-muted-foreground h-16 w-16" />
                <h1 className="text-2xl font-semibold">Shared Chat Not Found</h1>
                <p className="text-muted-foreground">This shared chat may have been deleted or the link is invalid.</p>
                <Button variant="outline" onClick={() => shared.navigate("/chat")}>
                    Go to Chat
                </Button>
            </div>
        );
    }

    const { session } = shared;

    // Header buttons
    const headerButtons = [
        <div key="shared-info" className="flex items-center gap-2 text-sm text-(--color-secondary-text-wMain)">
            <Tooltip>
                <TooltipTrigger asChild>
                    <span className="inline-flex cursor-pointer">
                        <UserLock className="h-4 w-4 text-(--color-secondary-wMain)" />
                    </span>
                </TooltipTrigger>
                <TooltipContent>
                    Shared by <span className="font-bold">{session.tasks[0]?.userId || "Unknown"}</span> on{" "}
                    <span className="font-bold">{formatDateYMD(session.createdTime)}</span>
                </TooltipContent>
            </Tooltip>
            <span className="text-muted-foreground text-xs">Viewer</span>
            {session.snapshotTime && (
                <>
                    <div className="bg-border h-4 w-px" />
                    <span className="text-muted-foreground text-xs">Snapshot from {formatDateYMD(session.snapshotTime)}</span>
                </>
            )}
        </div>,
        session?.isOwner && session?.sessionId ? (
            <Button key="go-to-chat" variant="outline" size="sm" onClick={() => shared.navigate(`/chat?sessionId=${session.sessionId}`)}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Go to Chat
            </Button>
        ) : null,
    ].filter(Boolean) as ReactNode[];

    return (
        <SharedChatProvider
            artifacts={shared.convertedArtifacts}
            ragData={shared.ragData}
            sessionId={shared.sessionIdForProvider}
            shareId={shared.shareId || ""}
            onOpenSidePanelTab={shared.handleProviderTabOpen}
            onSetTaskIdInSidePanel={shared.setSelectedTaskId}
        >
            <div className="relative flex h-screen w-full flex-col overflow-hidden">
                <Header title={session.title} buttons={headerButtons} />

                <div className="flex min-h-0 flex-1">
                    <div className="min-h-0 flex-1 overflow-x-auto">
                        <ResizablePanelGroup direction="horizontal" autoSaveId="shared-chat-view-side-panel" className="h-full">
                            {/* Messages panel */}
                            <ResizablePanel defaultSize={shared.isSidePanelCollapsed ? 96 : 70} minSize={50} id="shared-chat-view-messages-panel">
                                <div className="flex h-full w-full flex-col">
                                    <div className="flex min-h-0 flex-1 flex-col py-6">
                                        <main className="h-full overflow-y-auto px-6">
                                            <div className="mx-auto max-w-3xl space-y-4">
                                                {shared.messages.length === 0 ? (
                                                    <div className="text-muted-foreground py-12 text-center">
                                                        <p>No messages in this shared chat.</p>
                                                    </div>
                                                ) : (
                                                    shared.messages.map((message, index) => {
                                                        const isLastWithTaskId = !!(message.taskId && shared.lastMessageIndexByTaskId.get(message.taskId) === index);
                                                        return (
                                                            <div key={message.metadata?.messageId || `msg-${index}`}>
                                                                <ChatMessage message={message} isLastWithTaskId={isLastWithTaskId} />
                                                            </div>
                                                        );
                                                    })
                                                )}
                                            </div>
                                        </main>

                                        {/* Read-only banner instead of ChatInputArea */}
                                        <div style={CHAT_STYLES}>
                                            <div className="bg-muted/50 border-border mx-auto flex max-w-3xl items-center gap-3 rounded-lg border px-4 py-3 shadow-sm backdrop-blur-sm">
                                                <Info className="text-muted-foreground h-5 w-5 flex-shrink-0" />
                                                <span className="text-muted-foreground text-sm">This chat is read-only. To build off of it, continue a new conversation.</span>
                                                {!(session?.isOwner && session?.sessionId) && (
                                                    <Button variant="outline" size="sm" onClick={shared.handleForkChat} disabled={shared.isForking} className="ml-auto flex-shrink-0">
                                                        {shared.isForking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquare className="mr-2 h-4 w-4" />}
                                                        Continue in New Chat
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </ResizablePanel>

                            <ResizableHandle />

                            {/* Side panel - always visible */}
                            <ResizablePanel
                                defaultSize={shared.isSidePanelCollapsed ? 4 : 30}
                                minSize={shared.isSidePanelCollapsed ? 4 : 20}
                                maxSize={shared.isSidePanelCollapsed ? 4 : 50}
                                id="shared-chat-view-side-panel"
                            >
                                <SharedSidePanel
                                    isCollapsed={shared.isSidePanelCollapsed}
                                    activeTab={shared.activeSidePanelTab}
                                    onTabChange={shared.setActiveSidePanelTab}
                                    onToggle={shared.toggleSidePanel}
                                    onOpenTab={shared.openSidePanelTab}
                                    hasRagSources={shared.hasRagSources}
                                    handleSharedArtifactDownload={shared.handleSharedArtifactDownload}
                                    session={session}
                                    selectedTaskId={shared.selectedTaskId}
                                    onTaskSelect={shared.setSelectedTaskId}
                                    ragData={shared.ragData}
                                />
                            </ResizablePanel>
                        </ResizablePanelGroup>
                    </div>
                </div>
            </div>
        </SharedChatProvider>
    );
}
