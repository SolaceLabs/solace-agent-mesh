/**
 * SharedSessionPage - Public view of a shared chat session (standalone, outside AppLayout)
 *
 * Uses the full ChatMessage component for pixel-perfect rendering parity with ChatPage.
 */

import { ArrowLeft, AlertCircle, Info, UserLock, MessageSquare, Loader2 } from "lucide-react";
import { Button, Spinner, ResizablePanelGroup, ResizablePanel, ResizableHandle, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { ChatMessage } from "@/lib/components/chat";
import { SharedChatProvider } from "@/lib/providers/SharedChatProvider";
import { SharedSidePanel } from "@/lib/components/share/SharedSidePanel";
import { useSharedSession, formatDateYMD } from "@/lib/hooks/useSharedSession";

export function SharedSessionPage() {
    const shared = useSharedSession();

    // Loading state
    if (shared.loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Spinner size="large" variant="primary">
                    <p className="text-muted-foreground mt-4 text-sm">Loading shared session...</p>
                </Spinner>
            </div>
        );
    }

    // Error state
    if (shared.error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-destructive h-16 w-16" />
                <h1 className="text-2xl font-semibold">Unable to View Shared Session</h1>
                <p className="text-muted-foreground max-w-md text-center">{shared.error}</p>
                <Button variant="outline" onClick={() => shared.navigate("/")}>
                    Go Home
                </Button>
            </div>
        );
    }

    // Not found state
    if (!shared.session) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-muted-foreground h-16 w-16" />
                <h1 className="text-2xl font-semibold">Shared Session Not Found</h1>
                <p className="text-muted-foreground">This shared session may have been deleted or the link is invalid.</p>
                <Button variant="outline" onClick={() => shared.navigate("/")}>
                    Go Home
                </Button>
            </div>
        );
    }

    const { session } = shared;

    return (
        <SharedChatProvider
            artifacts={shared.convertedArtifacts}
            ragData={shared.ragData}
            sessionId={shared.sessionIdForProvider}
            shareId={shared.shareId || ""}
            onOpenSidePanelTab={shared.handleProviderTabOpen}
            onSetTaskIdInSidePanel={shared.setSelectedTaskId}
        >
            <div className="flex h-screen flex-col">
                {/* Header */}
                <header className="border-b px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Button variant="ghost" size="sm" onClick={() => shared.navigate("/")}>
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Button>
                            <div className="h-6 border-r" />
                            <div>
                                <h1 className="text-lg font-semibold">{session.title}</h1>
                            </div>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className="flex items-center gap-2 text-sm text-(--color-secondary-text-wMain)">
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span className="inline-flex cursor-pointer">
                                            <UserLock className="h-4 w-4 text-(--color-secondary-wMain)" />
                                        </span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        You are a <span className="font-bold">viewer</span> of this chat
                                    </TooltipContent>
                                </Tooltip>
                                <span>Viewer</span>
                                <div className="bg-border h-4 w-px" />
                                {session.snapshotTime ? (
                                    <span>
                                        Snapshot from <span className="font-bold">{formatDateYMD(session.snapshotTime)}</span>
                                    </span>
                                ) : (
                                    <span>
                                        Shared by <span className="font-bold">{session.tasks[0]?.userId || "Unknown"}</span> on{" "}
                                        <span className="font-bold">{formatDateYMD(session.createdTime)}</span>
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </header>

                {/* Main content with resizable panels */}
                <div className="relative min-h-0 flex-1">
                    <ResizablePanelGroup direction="horizontal" autoSaveId="shared-session-side-panel" className="h-full">
                        {/* Messages panel */}
                        <ResizablePanel defaultSize={shared.isSidePanelCollapsed ? 96 : 70} minSize={50} id="shared-session-messages-panel">
                            <div className="relative flex h-full flex-col">
                                <main className="min-h-0 flex-1 overflow-y-auto p-6">
                                    <div className="mx-auto max-w-3xl space-y-4">
                                        {shared.messages.length === 0 ? (
                                            <div className="text-muted-foreground py-12 text-center">
                                                <p>No messages in this session.</p>
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
                                {/* Read-only banner pinned to bottom */}
                                <div className="z-10 flex-shrink-0 px-6 pt-2 pb-4">
                                    <div className="bg-muted/50 border-border mx-auto flex max-w-3xl items-center gap-3 rounded-lg border px-4 py-3 shadow-sm backdrop-blur-sm">
                                        <Info className="text-muted-foreground h-5 w-5 flex-shrink-0" />
                                        <span className="text-muted-foreground text-sm">This chat is read-only. To build off of it, continue a new conversation.</span>
                                        <Button variant="outline" size="sm" onClick={shared.handleForkChat} disabled={shared.isForking} className="ml-auto flex-shrink-0">
                                            {shared.isForking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquare className="mr-2 h-4 w-4" />}
                                            Continue in New Chat
                                        </Button>
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
                            id="shared-session-side-panel"
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
        </SharedChatProvider>
    );
}
