# Implementation Guide: Agent-Specific Minimal Chat Page

## What This Implements

A new URL pattern `/#/:agentName/chat` (e.g. `/#/OrchestratorAgent/chat`) that opens a minimal, embeddable chat page locked to a single SAM agent. Four optional query parameters control the UI chrome:

| Parameter | Default | Effect |
|---|---|---|
| `header=true` | off | Shows the top header bar with the agent name, a "Show Chat Sessions" button, and a "Start New Chat" button |
| `menu=true` | off | Shows the left navigation sidebar |
| `panel=true` | off | Shows the right activity/info panel (resizable) |

Parameters can be combined freely:

| URL | Header | Left menu | Right panel |
|---|---|---|---|
| `/#/OrchestratorAgent/chat` | — | — | — |
| `/#/OrchestratorAgent/chat?header=true` | ✅ | — | — |
| `/#/OrchestratorAgent/chat?menu=true` | — | ✅ | — |
| `/#/OrchestratorAgent/chat?panel=true` | — | — | ✅ |
| `/#/OrchestratorAgent/chat?header=true&menu=true&panel=true` | ✅ | ✅ | ✅ |

The `agentName` in the URL must exactly match the `agent_name` field in the agent's YAML config (e.g. `OrchestratorAgent`, `HappyAgent`).

The existing `/#/chat` page and all other routes are **completely untouched**.

---

## Prerequisites

- Node.js and npm installed
- Frontend source at `client/webui/frontend/`
- Familiarity with React, React Router v6, and TypeScript

---

## Step 1 — Create `AgentChatPage.tsx`

Create a new file:
```
src/lib/components/pages/AgentChatPage.tsx
```

This is the core new page. It reuses the same chat components as `ChatPage` but removes the always-on header, session panel, and share functionality. The agent is locked from the URL path param; the header, right panel, left menu, and session panel are all conditionally shown via query parameters.

**Full file content:**

```tsx
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

    // Only expose the locked agent to the input area
    const lockedAgents = useMemo(() => {
        if (!agentName) return agents;
        return agents.filter(a => a.name === agentName);
    }, [agents, agentName]);

    // Right side panel handlers — mirrors ChatPage exactly
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

    // Shared chat content — used in both layout variants (with/without right panel)
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
            {/* Session history sliding panel — only when header is shown and not using new nav */}
            {showHeader && !useNewNav && (
                <div
                    inert={isSessionSidePanelCollapsed}
                    className={`absolute top-0 left-0 z-20 h-screen transition-[transform,visibility] duration-300 ${isSessionSidePanelCollapsed ? "invisible -translate-x-full delay-300" : "visible translate-x-0"}`}
                >
                    <SessionSidePanel onToggle={handleSessionSidePanelToggle} />
                </div>
            )}
            {/* Header bar with agent name and session controls */}
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
            {/* Main content area — shifts right when session panel is open */}
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
```

---

## Step 2 — Add `hideAgentSelector` prop to `ChatInputArea`

File: `src/lib/components/chat/ChatInputArea.tsx`

**Change 1 — props interface** (around line 63):

```tsx
// BEFORE:
export const ChatInputArea: React.FC<{
    agents: AgentCardInfo[];
    scrollToBottom?: () => void;
}> = ({ agents = [], scrollToBottom }) => {

// AFTER:
export const ChatInputArea: React.FC<{
    agents: AgentCardInfo[];
    scrollToBottom?: () => void;
    hideAgentSelector?: boolean;
}> = ({ agents = [], scrollToBottom, hideAgentSelector = false }) => {
```

**Change 2 — wrap the agent Select in a conditional** (find the block that starts with `<div className="hidden @[480px]:block">Agent: </div>`):

```tsx
// BEFORE:
<div className="hidden @[480px]:block">Agent: </div>
<Select
    value={selectedAgentName}
    onValueChange={agentName => {
        handleAgentSelection(agentName);
    }}
    disabled={isResponding || agents.length === 0}
>
    <SelectTrigger className="w-[250px]">
        <SelectValue placeholder="Select an agent..." />
    </SelectTrigger>
    <SelectContent>
        {agents
            .filter(agent => !agent.isWorkflow)
            .map(agent => (
                <SelectItem key={agent.name} value={agent.name}>
                    {agent.displayName || agent.name}
                </SelectItem>
            ))}
    </SelectContent>
</Select>

// AFTER:
{!hideAgentSelector && (
    <>
        <div className="hidden @[480px]:block">Agent: </div>
        <Select
            value={selectedAgentName}
            onValueChange={agentName => {
                handleAgentSelection(agentName);
            }}
            disabled={isResponding || agents.length === 0}
        >
            <SelectTrigger className="w-[250px]">
                <SelectValue placeholder="Select an agent..." />
            </SelectTrigger>
            <SelectContent>
                {agents
                    .filter(agent => !agent.isWorkflow)
                    .map(agent => (
                        <SelectItem key={agent.name} value={agent.name}>
                            {agent.displayName || agent.name}
                        </SelectItem>
                    ))}
            </SelectContent>
        </Select>
    </>
)}
```

No other logic in `ChatInputArea` was changed. The `/#/chat` page passes no `hideAgentSelector` prop so it defaults to `false` and the selector renders exactly as before.

---

## Step 3 — Export the new page from the pages barrel

File: `src/lib/components/pages/index.ts`

Add this line at the top:

```ts
export { AgentChatPage } from "./AgentChatPage";
```

---

## Step 4 — Register the route in the router

File: `src/router.tsx`

**Change 1 — add `AgentChatPage` to the import:**

```ts
// BEFORE:
import { AgentMeshPage, ArtifactsPage, ChatPage, ProjectsPage, PromptsPage,
         RecentChatsPage, ScheduledTasksPage, SharedChatViewPage } from "./lib";

// AFTER:
import { AgentChatPage, AgentMeshPage, ArtifactsPage, ChatPage, ProjectsPage,
         PromptsPage, RecentChatsPage, ScheduledTasksPage, SharedChatViewPage } from "./lib";
```

**Change 2 — add the route** inside the AppLayout `children` array, just before the `*` catch-all:

```ts
{
    path: ":agentName/chat",
    element: <AgentChatPage />,
},
```

> **Why this doesn't conflict:** React Router v6 always prefers static path segments over dynamic ones. All existing routes (`chat`, `agents`, `projects`, etc.) are static and always win. The pattern `:agentName/chat` only matches two-segment paths ending in `/chat` that don't start with a known static route name.

---

## Step 5 — Control the left sidebar via `?menu=true`

File: `src/AppLayout.tsx`

**Change 1 — add `useSearchParams` to the react-router-dom import:**

```ts
// BEFORE:
import { Outlet, useLocation, useNavigate } from "react-router-dom";

// AFTER:
import { Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
```

**Change 2 — update `isMinimalRoute`** inside `AppLayoutContent`:

```tsx
// BEFORE:
const isMinimalRoute = /^\/[^/]+\/chat$/.test(location.pathname);

// AFTER:
const [searchParams] = useSearchParams();
const isMinimalRoute = /^\/[^/]+\/chat$/.test(location.pathname)
    && searchParams.get("menu") !== "true";
```

The sidebar render block `{!isMinimalRoute && (...)}` needs no further changes.

**How the logic works:**
- The regex `^\/[^/]+\/chat$` matches two-segment paths ending in `/chat` (e.g. `/OrchestratorAgent/chat`)
- `/chat` is a single segment — does **not** match, so the standard chat page always shows its sidebar
- `?menu=true` flips `isMinimalRoute` to `false`, restoring the sidebar on the agent chat page

---

## Step 6 — Build and deploy

```bash
cd client/webui/frontend

# Install dependencies if node_modules is absent
npm install

# Build (output goes to frontend/static/)
npm run build

# Copy built files to wherever SAM serves static assets from
# Adjust the destination path to match your SAM installation
cp -r static/* <SAM_INSTALL_PATH>/client/webui/frontend/static/
```

Restart the SAM process after deploying.

---

## Verification Checklist

After deploying, open a browser and confirm the following:

- [ ] `/#/chat` — full page unchanged: sidebar, right panel, agent selector, header all present
- [ ] `/#/<AgentName>/chat` — bare chat: no header, no sidebar, no right panel, no agent selector; correct agent pre-selected
- [ ] `/#/<AgentName>/chat?header=true` — header appears with agent name as title; "Show Chat Sessions" (panel icon) and "Start New Chat" (pencil icon) buttons visible in header
- [ ] Clicking "Show Chat Sessions" in the header slides open the session history panel from the left
- [ ] Clicking "Start New Chat" clears the conversation and starts a fresh session
- [ ] `/#/<AgentName>/chat?menu=true` — left navigation sidebar visible; header and right panel still hidden
- [ ] `/#/<AgentName>/chat?panel=true` — right activity panel visible and resizable; header and sidebar still hidden
- [ ] `/#/<AgentName>/chat?header=true&menu=true&panel=true` — all three UI elements visible simultaneously
- [ ] Sending a message in any `/:agentName/chat` variant returns a response from the correct agent
- [ ] An unknown agent name (e.g. `/#/nonexistent/chat`) loads without crashing
