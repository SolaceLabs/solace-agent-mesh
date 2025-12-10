# SAM Apps Feature - Architecture & Implementation Plan

**Version:** 1.1
**Date:** December 6, 2024
**Status:** Planning - Updated with Full Page UI Design

## Executive Summary

The SAM Apps feature enables users to build fully-fledged HTML-based applications that run in the SAM UI within secure iframes. These apps are created through conversation with a dedicated **App Agent** that orchestrates code generation using Claude Code tools, providing users with the ability to create custom dashboards, data visualizations, and interactive tools tailored to their specific needs.

### Key Capabilities

- **Agent-Orchestrated Development**: Apps are built through natural conversation with the App Agent, which autonomously manages all code generation and workspace operations
- **Lightning-Fast Creation**: Specialized Docker image with pre-built template enables app creation in 12-15 seconds (20-30x faster than standard setup)
- **Conversational Workflow**: Multi-turn dialogue for requirements gathering, iterative development, and refinement
- **Full-Stack Framework**: React 19 + Vite + Tailwind + TypeScript pre-configured with hot reload
- **Live Preview**: Containerized Vite dev servers provide instant feedback as the agent builds features
- **SAM Integration**: Apps can call agents, access LLMs, manage artifacts, and persist data via @sam/sdk
- **Isolated Execution**: Each app runs in a sandboxed iframe with per-app storage
- **Build Validation**: Agent analyzes and fixes build errors through error feedback loop
- **Version Control**: Git-based versioning through automated workspace management

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [User Experience Flow](#user-experience-flow)
3. [App Creation UI Architecture](#app-creation-ui-architecture)
4. [SAM SDK Design](#sam-sdk-design)
5. [Backend Infrastructure](#backend-infrastructure)
6. [Frontend Integration](#frontend-integration)
7. [Claude Code Integration](#claude-code-integration)
8. [App Lifecycle Management](#app-lifecycle-management)
9. [Security Model](#security-model)
10. [Implementation Roadmap](#implementation-roadmap)
11. [API Reference](#api-reference)
12. [Examples](#examples)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SAM UI (Parent)                          │
│  ┌────────────┬────────────┬────────────┬──────────────────┐   │
│  │   Chats    │  Projects  │  Prompts   │   Apps (NEW)     │   │
│  └────────────┴────────────┴────────────┴──────────────────┘   │
│                                                                   │
│  User creates app → Backend creates workspace → Session with App Agent
│  User converses with App Agent → Agent builds via claude-code
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              App Frame (iframe container)                │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │          User's App (AI-Generated)                │  │   │
│  │  │  ┌─────────────────────────────────────────────┐  │  │   │
│  │  │  │  React Components + SAM SDK                 │  │  │   │
│  │  │  │  - Agent Calls                              │  │  │   │
│  │  │  │  - LLM Access                               │  │  │   │
│  │  │  │  - Artifact Management                      │  │  │   │
│  │  │  │  - Storage (key-value)                      │  │  │   │
│  │  │  └─────────────────────────────────────────────┘  │  │   │
│  │  │          ▲                                         │  │   │
│  │  │          │ @sam/sdk (TypeScript)                  │  │   │
│  │  │          │                                         │  │   │
│  │  │          │ postMessage (init) + REST/SSE (runtime)│  │   │
│  │  └──────────┼─────────────────────────────────────────┘  │   │
│  └─────────────┼─────────────────────────────────────────────┘   │
│                │                                                   │
└────────────────┼───────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SAM Backend (FastAPI)                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Existing Routers:                                         │ │
│  │  - /message:stream (agent calls) ← App Agent               │ │
│  │  - /artifacts/* (upload, download, list, delete)           │ │
│  │  - /tasks/* (list, get, events)                            │ │
│  │  - /sessions/* (CRUD) ← App Agent sessions                 │ │
│  │  - /agentCards (list agents)                               │ │
│  │  - /people/search (user search)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  NEW Routers (for Apps):                                   │ │
│  │  - /apps/* (CRUD, workspace mgmt, deploy, dev server)      │ │
│  │  - /storage/* (per-app key-value storage)                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    App Agent (SAM Agent)                   │ │
│  │  - Orchestrates app building via conversation              │ │
│  │  - Uses claude-code tools for code generation              │ │
│  │  - Manages requirements, design, implementation            │ │
│  │  - Analyzes and fixes build errors                         │ │
│  └───────────────────┬────────────────────────────────────────┘ │
└────────────────────────┼──────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Claude Code Tools (Containerized)                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Workspace Type: "app"                                     │ │
│  │  Environment: sam-app (React + Vite + Tailwind)            │ │
│  │  Pre-installed: @sam/sdk package, all dependencies         │ │
│  │  Git: Automatic versioning                                 │ │
│  │  Testing: Build validation + linting                       │ │
│  │                                                             │ │
│  │  Tools used by App Agent:                                  │ │
│  │  - claude_code_execute (code generation, builds)           │ │
│  │  - claude_code_read_files (inspect generated code)         │ │
│  │  - claude_code_list_workspaces (workspace management)      │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### 1. **SAM UI (Parent Frame)**
- Navigation to /apps route
- Apps list/grid view
- App creation form (name, description)
- Session management with App Agent
- App iframe container with security controls
- postMessage initialization handshake
- Theme propagation (dark/light mode)
- Live preview toggle and display

#### 2. **App Agent** (SAM Agent)
- **Orchestrates all app building** through conversation with user
- Gathers requirements via multi-turn dialogue
- Designs application architecture (components, data flow, SAM integrations)
- Generates code using claude_code_execute tool
- Manages incremental development (one feature at a time)
- Analyzes and fixes build errors
- Provides progress updates via status messages
- Suggests testing and validation before deployment

#### 3. **User's App (Iframe)**
- React 19 + TypeScript + Tailwind
- SAM SDK for platform integration
- Custom UI/UX built by App Agent
- Isolated storage namespace
- Direct API access to SAM backend

#### 4. **SAM SDK** (`@sam/sdk`)
- TypeScript library pre-installed in app templates
- Modules: auth, agents, llm, artifacts, storage, tasks, ui
- React hooks for ergonomic integration
- EventSource for streaming responses
- Type-safe API with full TypeScript support

#### 5. **SAM Backend**
- Existing routers for agent calling, artifacts, tasks, sessions
- NEW: Apps router for CRUD, workspace management, dev servers, deployment
- NEW: Storage router for app-scoped key-value persistence
- Authentication & authorization
- Rate limiting via user quotas
- Containerized dev server management (Vite)

#### 6. **Claude Code Tools**
- Containerized development environment (used by App Agent)
- Workspace management (git, build, test)
- Multi-turn AI coding sessions
- Hot reload during development
- Build validation before deployment
- Specialized sam-app environment with pre-built template

---

## User Experience Flow

### App Creation Flow (Agent-Orchestrated)

```
1. User navigates to /apps page
   └─> Sees list of their existing apps

2. User clicks "New App" button
   └─> Modal or page displays form:
       - App Name (required)
       - Description (optional)
       - "Create" button

3. User fills form and clicks "Create"
   └─> Frontend POST /api/v1/apps (name, description)

4. Backend creates app infrastructure:
   ├─> Insert into apps table (app_id, user_id, name, description, status='draft')
   ├─> Create workspace directory: /workspaces/{user_id}/apps/{app_id}/
   ├─> Copy pre-built template from claude-code-sam-app Docker image (/opt/app-template)
   ├─> Update package.json with app name
   ├─> Initialize git repository
   ├─> Generate CLAUDE.md with app context + full SAM SDK documentation
   └─> Return app_id and workspace_path to frontend

5. Frontend auto-creates session with App Agent:
   ├─> POST /api/v1/sessions (agent_id="AppAgent")
   ├─> Auto-send first message: "I want to build [name]: [description]. Help me refine requirements and create this app."
   └─> Navigate to /apps/{app_id}/edit (full page: chat left, preview right)

6. App Agent responds (Requirements Phase):
   ├─> Reviews app name and description
   ├─> Asks clarifying questions about features, data sources, UI/UX
   ├─> Suggests technology approaches and SAM agent integrations
   └─> Status updates streamed to UI chat

7. User refines requirements (Multi-Turn Conversation):
   ├─> User answers agent's questions
   ├─> Agent proposes implementation plan
   ├─> User approves or requests changes
   └─> Agent finalizes design

8. Agent builds app incrementally:

   **Turn 1: Initial Setup**
   └─> Agent calls claude_code_execute:
       "Set up React app structure with components for [features]"
   ├─> Creates React components, sets up routing
   ├─> Adds SAM SDK calls for agent integration
   ├─> Runs npm run build
   ├─> Status updates shown in chat: "Creating Dashboard.tsx...", "Running build..."
   ├─> Build succeeds
   └─> UI enables "Preview" button

   **User clicks "Preview" button**
   └─> UI requests /api/v1/apps/preview/{app_id}/
   ├─> Backend checks if dev server container exists
   ├─> If not: Start containerized Vite dev server on internal Docker network
   ├─> Proxy request to container's internal IP (e.g., http://172.18.0.5:5173)
   └─> App loads in preview pane with hot reload enabled

   **Turn 2: Add Features**
   User: "Add a bar chart showing monthly sales from the sales-data agent"

   └─> Agent calls claude_code_execute:
       "Add BarChart component that calls SAM.agents.call('sales-data')"
   ├─> Modifies components to fetch data via SAM SDK
   ├─> Vite HMR (Hot Module Replacement) detects file changes
   ├─> WebSocket sends HMR update through backend proxy
   └─> Preview iframe updates INSTANTLY (no full refresh, state preserved)

   **Turn 3: Iterate and Refine**
   User: "Make the chart responsive and add dark mode support"

   └─> Agent calls claude_code_execute again
   ├─> Applies Tailwind responsive classes
   ├─> Adds dark mode toggle using SAM.ui.getTheme()
   ├─> Hot reload updates preview
   └─> User sees polished UI instantly

9. User clicks "Save & Deploy":
   └─> UI calls POST /api/v1/apps/{app_id}/deploy
   ├─> Backend runs `npm run build` in container
   ├─> **If build succeeds:**
   │   ├─> Copy dist/ to /workspaces/{user}/apps-deployed/{app_id}/v1/
   │   ├─> Update current symlink
   │   ├─> Create git tag v1
   │   ├─> Update DB (status='deployed', current_version=1)
   │   ├─> Stop dev server container
   │   └─> Return success
   └─> **If build fails:**
       ├─> UI shows dialog with build errors (TypeScript, linting, etc.)
       ├─> User clicks "Send to Agent" button
       ├─> UI injects error message into chat: "Build failed with errors: [errors]"
       ├─> Agent receives errors, analyzes them
       ├─> Agent calls claude_code_execute to fix errors
       └─> Retry deployment

10. User accesses deployed app:
    ├─> Navigate to /apps (apps list)
    ├─> Click app card
    ├─> UI loads app in full-screen iframe
    ├─> App served from /workspaces/{user}/apps-deployed/{app_id}/current/
    ├─> postMessage handshake initializes SAM SDK in app
    └─> App renders with full SAM platform integration
```

### App Usage Flow

```
1. User navigates to /apps
   └─> Sees grid of available apps

2. User clicks app
   └─> SAM UI creates AppFrame component
   └─> Mounts iframe with sandbox attributes
   └─> Serves app from workspace build output

3. Iframe loads app
   └─> App imports SAM SDK
   └─> SDK sends "ready" postMessage to parent

4. Parent responds with initialization data
   {
     type: "init",
     authToken: "...",
     apiEndpoint: "https://sam.example.com/api/v1",
     user: { id, email, displayName },
     theme: "dark",
     appId: "user-dashboard"
   }

5. SDK initializes
   └─> Stores auth token in memory
   └─> Sets up API client
   └─> Emits "initialized" event

6. App renders
   └─> Makes agent calls via SAM.agents.call()
   └─> Fetches data via SAM.storage.get()
   └─> Displays UI with theme inherited from parent

7. Hot reload (during development)
   └─> User requests changes via coding agent
   └─> Agent modifies code
   └─> Vite hot-reloads iframe
   └─> Changes appear immediately
```

---

## App Creation UI Architecture

### Overview

The app creation experience is a full-page interface that combines a chat-based development workflow with live preview capability. This enables users to iteratively build applications through natural language conversation with an AI coding agent while seeing changes in real-time.

### Component Hierarchy

```
CreateAppPage (route: /apps/new or /apps/:appId/edit)
├── AppCreationHeader
│   ├── Back button
│   ├── App name input
│   ├── Preview toggle button
│   └── Save & Deploy button
├── Main Content (flex container)
│   ├── ChatPane (left, resizable)
│   │   ├── ChatMessageList (reused from main chat)
│   │   │   ├── User messages
│   │   │   ├── Agent messages
│   │   │   ├── Status updates (from claude-code streaming)
│   │   │   └── Artifact notifications
│   │   └── ChatInput (reused from main chat)
│   │       ├── Textarea for prompt
│   │       ├── Send button
│   │       └── File attachment (optional)
│   └── PreviewPane (right, toggleable)
│       ├── Preview controls (refresh, open in new tab)
│       ├── AppPreviewFrame (iframe)
│       │   └── Vite dev server output (with HMR)
│       └── Console output (errors/warnings)
```

### CreateAppPage Component

**File:** `client/webui/frontend/src/pages/CreateAppPage.tsx`

```typescript
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { ChatInput } from '@/components/chat/ChatInput';
import { AppPreviewFrame } from '@/components/apps/AppPreviewFrame';
import { useAppCreationChat } from '@/lib/hooks/useAppCreationChat';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

export function CreateAppPage() {
  const { appId } = useParams<{ appId?: string }>();
  const navigate = useNavigate();
  const isNewApp = appId === 'new';

  // State
  const [appName, setAppName] = useState('');
  const [showPreview, setShowPreview] = useState(false);

  // App creation chat hook
  const {
    sessionId,
    workspaceId,
    workspacePath,
    messages,
    isResponding,
    buildStatus,
    handleSubmit,
    handleSaveAndDeploy,
  } = useAppCreationChat(appId, appName);

  // Auto-show preview when build succeeds
  useEffect(() => {
    if (buildStatus === 'success' && !showPreview) {
      // Show preview automatically on first successful build
      setShowPreview(true);
    }
  }, [buildStatus]);

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <div className="border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/apps')}
          >
            ← Back to Apps
          </Button>
          <Input
            placeholder="App Name"
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            className="w-64"
          />
        </div>

        <div className="flex items-center gap-2">
          {buildStatus === 'success' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPreview(!showPreview)}
            >
              {showPreview ? 'Hide Preview' : 'Show Preview'}
            </Button>
          )}
          <Button
            onClick={handleSaveAndDeploy}
            disabled={buildStatus !== 'success' || !appName}
          >
            Save & Deploy
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Pane */}
        <div
          className={`flex flex-col transition-all duration-300 ${
            showPreview ? 'w-1/2' : 'w-full'
          }`}
        >
          {/* Messages */}
          <div className="flex-1 overflow-auto">
            <ChatMessageList
              messages={messages}
              isResponding={isResponding}
            />
          </div>

          {/* Input */}
          <div className="border-t p-4">
            <ChatInput
              onSubmit={handleSubmit}
              disabled={isResponding}
              placeholder="Tell the AI what to build or modify..."
            />
          </div>
        </div>

        {/* Preview Pane */}
        {showPreview && (
          <div className="w-1/2 border-l flex flex-col">
            {/* Preview Header */}
            <div className="border-b px-4 py-2 flex items-center justify-between bg-muted/50">
              <span className="text-sm font-medium">Live Preview</span>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.open(`/apps/preview/${workspaceId}`, '_blank')}
                >
                  Open in New Tab
                </Button>
              </div>
            </div>

            {/* Preview Iframe */}
            <div className="flex-1 overflow-hidden">
              {workspacePath ? (
                <AppPreviewFrame
                  workspacePath={workspacePath}
                  workspaceId={workspaceId}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Waiting for first build...
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

### useAppCreationChat Hook

**File:** `client/webui/frontend/src/lib/hooks/useAppCreationChat.ts`

```typescript
import { useState, useEffect, useCallback } from 'react';
import { useAuthContext } from '@/lib/contexts/AuthContext';
import { useConfigContext } from '@/lib/contexts/ConfigContext';
import { Message } from '@/lib/types';

interface AppCreationChatState {
  sessionId: string | null;
  workspaceId: string;
  workspacePath: string | null;
  messages: Message[];
  isResponding: boolean;
  buildStatus: 'idle' | 'building' | 'success' | 'error';
  handleSubmit: (prompt: string) => Promise<void>;
  handleSaveAndDeploy: () => Promise<void>;
}

export function useAppCreationChat(
  appId: string | undefined,
  appName: string
): AppCreationChatState {
  const { user } = useAuthContext();
  const { configServerUrl } = useConfigContext();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [workspaceId] = useState(() =>
    appId === 'new'
      ? `app-${Date.now()}`
      : appId || ''
  );
  const [workspacePath, setWorkspacePath] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isResponding, setIsResponding] = useState(false);
  const [buildStatus, setBuildStatus] = useState<'idle' | 'building' | 'success' | 'error'>('idle');

  // Initialize session with app-builder agent
  useEffect(() => {
    initializeSession();
  }, []);

  const initializeSession = async () => {
    try {
      // Create session with app-builder agent
      const response = await fetch(`${configServerUrl}/api/v1/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({
          agentId: 'app-builder',
          workspaceId,
          workspaceName: appName || 'New App',
        }),
      });

      const session = await response.json();
      setSessionId(session.sessionId);

      // Add welcome message
      setMessages([{
        role: 'assistant',
        content: `Hi! I'm your app builder assistant. I'll help you create a React application that runs in SAM. What would you like to build?`,
        timestamp: Date.now(),
      }]);
    } catch (error) {
      console.error('Failed to initialize session:', error);
    }
  };

  const handleSubmit = useCallback(async (prompt: string) => {
    if (!sessionId || isResponding) return;

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsResponding(true);

    // Create placeholder for agent response
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      // Call agent with claude_code_execute tool
      const response = await fetch(`${configServerUrl}/api/v1/agent/send-streaming-message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({
          sessionId,
          message: prompt,
        }),
      });

      // Set up SSE for streaming
      const eventSource = new EventSource(
        `${configServerUrl}/api/v1/tasks/${response.headers.get('X-Task-ID')}/events`
      );

      eventSource.addEventListener('TaskStatusUpdateEvent', (event) => {
        const data = JSON.parse(event.data);

        // Update assistant message with status
        if (data.statusText) {
          setMessages(prev => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: updated[updated.length - 1].content + '\n\n' + data.statusText,
            };
            return updated;
          });
        }

        // Track build status
        if (data.statusText?.includes('npm run build')) {
          setBuildStatus('building');
        }
        if (data.statusText?.includes('Build succeeded')) {
          setBuildStatus('success');
        }
        if (data.statusText?.includes('Build failed')) {
          setBuildStatus('error');
        }

        // Extract workspace path
        if (data.workspace_path) {
          setWorkspacePath(data.workspace_path);
        }
      });

      eventSource.addEventListener('TaskTextUpdateEvent', (event) => {
        const data = JSON.parse(event.data);

        // Append text chunk to assistant message
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: updated[updated.length - 1].content + data.text,
          };
          return updated;
        });
      });

      eventSource.addEventListener('TaskCompleteEvent', () => {
        eventSource.close();
        setIsResponding(false);
      });

      eventSource.addEventListener('error', () => {
        eventSource.close();
        setIsResponding(false);
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsResponding(false);
    }
  }, [sessionId, isResponding, configServerUrl]);

  const handleSaveAndDeploy = useCallback(async () => {
    if (!workspaceId || !appName) return;

    try {
      await fetch(`${configServerUrl}/api/v1/apps`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({
          workspaceId,
          name: appName,
          workspacePath,
        }),
      });

      // Navigate to apps list
      window.location.href = '/apps';
    } catch (error) {
      console.error('Failed to save app:', error);
    }
  }, [workspaceId, appName, workspacePath, configServerUrl]);

  return {
    sessionId,
    workspaceId,
    workspacePath,
    messages,
    isResponding,
    buildStatus,
    handleSubmit,
    handleSaveAndDeploy,
  };
}
```

### AppPreviewFrame Component (Hot Reload)

**File:** `client/webui/frontend/src/components/apps/AppPreviewFrame.tsx`

```typescript
import { useEffect, useRef, useState } from 'react';
import { useAuthContext } from '@/lib/contexts/AuthContext';
import { useThemeContext } from '@/lib/contexts/ThemeContext';
import { useConfigContext } from '@/lib/contexts/ConfigContext';

interface AppPreviewFrameProps {
  workspacePath: string;
  workspaceId: string;
}

export function AppPreviewFrame({ workspacePath, workspaceId }: AppPreviewFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { user } = useAuthContext();
  const { theme } = useThemeContext();
  const { configServerUrl } = useConfigContext();
  const [previewUrl, setPreviewUrl] = useState<string>('');

  useEffect(() => {
    // Start Vite dev server for this workspace
    startDevServer();
  }, [workspacePath]);

  const startDevServer = async () => {
    try {
      // Request backend to start Vite dev server for workspace
      const response = await fetch(`${configServerUrl}/api/v1/apps/dev-server`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`,
        },
        body: JSON.stringify({
          workspaceId,
          workspacePath,
        }),
      });

      const data = await response.json();

      // Dev server returns URL like http://localhost:5173
      setPreviewUrl(data.devServerUrl);
    } catch (error) {
      console.error('Failed to start dev server:', error);
    }
  };

  useEffect(() => {
    if (!previewUrl || !iframeRef.current) return;

    const iframe = iframeRef.current;

    // Wait for iframe to load
    iframe.onload = () => {
      // Send initialization message to app
      iframe.contentWindow?.postMessage({
        type: 'init',
        authToken: getAccessToken(),
        apiEndpoint: `${configServerUrl}/api/v1`,
        user: {
          id: user.userId,
          email: user.email,
          displayName: user.displayName,
        },
        theme: theme,
        appId: workspaceId,
      }, '*');
    };

    // Listen for messages from app
    const handleMessage = (event: MessageEvent) => {
      if (event.source !== iframe.contentWindow) return;

      const { type, payload } = event.data;

      switch (type) {
        case 'ready':
          console.log('Preview app ready');
          break;
        case 'error':
          console.error('Preview app error:', payload);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [previewUrl, user, theme]);

  if (!previewUrl) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Starting dev server...</p>
        </div>
      </div>
    );
  }

  return (
    <iframe
      ref={iframeRef}
      src={previewUrl}
      sandbox="allow-scripts allow-same-origin"
      className="w-full h-full border-0"
      title="App Preview"
    />
  );
}
```

**How Hot Reload Works:**

1. **Vite Dev Server**: Backend starts a Vite dev server for the workspace on a random port
2. **iframe Source**: Preview iframe points to the Vite dev server URL (e.g., `http://localhost:5173`)
3. **Vite HMR (Hot Module Replacement)**: When claude-code modifies files, Vite automatically:
   - Detects file changes via file system watcher
   - Sends HMR updates to browser via WebSocket
   - Updates only changed modules without full page reload
   - Preserves React component state
4. **User Experience**: User sees changes appear instantly in preview pane without losing state

### app-builder Agent Configuration

**File:** `examples/agents/app-builder.yaml`

```yaml
agent_name: app-builder
display_name: "App Builder"
description: "AI assistant that builds React applications using claude-code tools"

# Claude Code tools for code generation
tools:
  - tool_type: dynamic
    provider_module: "solace_agent_mesh.agent.tools.claude_code.tool_provider"
    provider_class: "ClaudeCodeToolProvider"
    tool_config:
      api_key: "${ANTHROPIC_API_KEY}"
      model: "claude-sonnet-4"
      workspace_base: "/var/sam/workspaces"
      settings_base: "/var/sam/settings"
      enable_streaming: true
      environment_variables:
        ANTHROPIC_BASE_URL: "${ANTHROPIC_BASE_URL}"

instruction: |
  You are an expert React developer that builds production-ready applications for the SAM platform.

  ## Your Role
  You help users create React applications that run in SAM's iframe-based app environment.
  You build apps incrementally through multi-turn conversations, showing progress after each step.

  ## Technical Stack
  - React 19 + TypeScript 5.8
  - Vite 6 (for dev server and builds)
  - Tailwind CSS 4 (for styling)
  - @sam/sdk (for SAM platform integration)

  ## Development Workflow
  1. **Initial Setup** (first turn):
     - Create project structure (src/, public/, etc.)
     - Set up package.json, tsconfig.json, vite.config.ts, tailwind.config.ts
     - Install dependencies: npm install
     - Create basic App.tsx with placeholder content
     - Run initial build: npm run build

  2. **Incremental Development** (subsequent turns):
     - Add ONE feature at a time based on user request
     - Make focused changes to specific files
     - Let Vite hot reload handle updates (do NOT run build after every change)
     - Only run build when user asks or when making major structural changes

  3. **SAM SDK Integration**:
     - Import: `import { SAM } from '@sam/sdk';`
     - Use SAM.agents.call() for agent calling
     - Use SAM.storage.set/get() for data persistence
     - Use SAM.artifacts.upload/download() for files
     - Always initialize SDK: `await SAM.ready();`

  4. **Code Quality**:
     - Use TypeScript for type safety
     - Follow React best practices (hooks, composition, single responsibility)
     - Use Tailwind for ALL styling (no inline styles)
     - Make apps responsive (mobile + desktop)
     - Handle errors gracefully

  5. **Build Validation**:
     - Run `npm run build` before user deploys
     - Run `npm run lint` to check for errors
     - Fix all TypeScript and linting errors
     - Verify build artifacts are created in dist/

  ## Communication Style
  - Be concise and action-oriented
  - Report what you're doing: "Creating components...", "Running build...", "Installing dependencies..."
  - Show file paths when editing: "Updated src/components/Dashboard.tsx"
  - Mention when build succeeds so user knows preview is ready
  - If you encounter errors, explain them clearly and fix them

  ## Important Rules
  - Do NOT ask for approval to run builds or tests
  - Do NOT create unnecessary abstractions or over-engineer
  - Do NOT add features the user didn't request
  - Do NOT skip build validation before deployment
  - Use claude_code_execute tool for all development tasks
  - Maintain the same workspace_id across all turns for session continuity
```

### Component Reuse from Existing Chat

The app creation UI reuses several components from the main SAM chat application:

**Reused Components:**

1. **ChatMessageList** (`lib/components/chat/ChatMessageList.tsx`)
   - Displays conversation history
   - Renders user and assistant messages
   - Shows status updates and artifacts
   - Handles markdown rendering

2. **ChatInput** (`lib/components/chat/ChatInput.tsx`)
   - Text input for prompts
   - File attachment support
   - Send button and keyboard shortcuts
   - Auto-resize textarea

3. **Message Types** (`lib/types/fe.ts`)
   - Reuse existing Message interface
   - TaskStatusUpdateEvent for progress
   - TaskTextUpdateEvent for streaming
   - TaskArtifactUpdateEvent for file notifications

4. **SSE Handling Pattern** (`lib/providers/ChatProvider.tsx`)
   - EventSource setup for streaming
   - Event listener patterns
   - Error handling and reconnection

**Benefits of Component Reuse:**

- Consistent UX between chat and app builder
- Less code to maintain
- Users already familiar with interface
- Shared bug fixes and improvements

---

## App Agent Architecture

### Overview

The App Agent is a dedicated SAM agent that orchestrates all app building through conversation with the user. Unlike the original design where the UI directly managed claude-code execution, the App Agent serves as an intelligent intermediary that owns the entire development workflow.

### Design Philosophy

The App Agent architecture embodies four core principles:

- **Agent-Centric**: The agent owns the development workflow, not the UI. The UI simply provides the interface for users to communicate with the agent, which then autonomously manages all code generation, workspace operations, and build validation.

- **Conversational**: Natural multi-turn dialogue enables the agent to understand requirements through questions and clarifications, rather than requiring users to provide complete specifications upfront.

- **Incremental**: Features are built one at a time with user feedback between iterations. This allows users to course-correct and refine the application as it develops, rather than waiting for a complete implementation.

- **Autonomous**: The agent independently uses claude-code tools to read files, write code, run builds, and fix errors without requiring explicit user approval for each operation.

### Agent Configuration

The App Agent is configured via standard SAM agent YAML configuration. See `examples/agents/app-agent.yaml` for the complete configuration.

**Key Configuration Elements:**

```yaml
agent_name: "AppAgent"
display_name: "App Builder"

tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
  - tool_type: python
    component_module: "solace_agent_mesh.agent.tools.claude_code.tool_provider"
    class_name: "ClaudeCodeToolProvider"
    tool_config:
      api_key: "${ANTHROPIC_API_KEY}"
      model: "vertex-claude-4-5-sonnet"
      workspace_base: "/var/sam/workspaces"
      settings_base: "/var/sam/settings"

session_service:
  type: "sql"
  database_url: "${APP_AGENT_DATABASE_URL}"
  default_behavior: "PERSISTENT"
```

The agent has access to:
- **claude_code_execute**: Primary tool for code generation, file operations, and builds
- **claude_code_read_files**: Inspect generated code
- **claude_code_list_workspaces**: Workspace management (rarely needed, workspace provided)
- **Artifact management tools**: For file uploads and downloads

### Workflow Pattern

The App Agent follows a structured 10-step workflow:

1. **App Creation**: User provides app name and description via UI form
2. **Workspace Initialization**: Backend creates workspace from Docker template (React + Vite + Tailwind + SAM SDK pre-installed)
3. **Session Auto-Start**: UI automatically creates session with App Agent
4. **Initial Message**: UI auto-sends first message: "I want to build [name]: [description]. Help me refine requirements and create this app."
5. **Requirements Gathering**: Agent asks clarifying questions about features, data sources, UI/UX preferences
6. **User Refinement**: Multi-turn conversation where user answers questions and refines vision
7. **Incremental Building**: Agent uses `claude_code_execute` to build features one at a time, reporting progress
8. **Live Preview**: User enables preview pane to see changes in real-time via containerized Vite dev server
9. **Iteration**: User requests changes, agent implements via `claude_code_execute`, hot reload updates preview
10. **Deployment**: User clicks "Save & Deploy", build validation runs, errors (if any) fed back to agent for fixing

### Agent Capabilities

The App Agent is designed with six core capabilities:

#### 1. Requirements Elicitation

The agent actively engages with users to understand their needs:
- Asks specific questions about desired features
- Clarifies ambiguous requirements
- Suggests technology approaches and design patterns
- Identifies which SAM agents could be integrated
- Proposes UI/UX patterns appropriate for the use case

#### 2. Architecture Design

Before writing code, the agent plans the application structure:
- Identifies React components needed
- Plans data flow and state management
- Designs SAM agent integration points (which agents to call, when, with what data)
- Proposes file/folder organization
- Considers responsive design requirements

#### 3. Code Generation

The agent uses `claude_code_execute` to write production-ready code:
- Creates React components with TypeScript
- Implements SAM SDK integration (`SAM.agents.call()`, `SAM.storage`, etc.)
- Applies Tailwind CSS for styling
- Follows React best practices (hooks, composition, single responsibility)
- Handles errors gracefully
- Makes apps responsive (mobile + desktop)

#### 4. Iteration

The agent responds to user feedback and refines implementation:
- Modifies existing components based on requests
- Adds new features incrementally
- Refactors code for clarity or performance
- Adjusts styling and layout
- Integrates additional SAM agents as needed

#### 5. Build Validation

Before deployment, the agent ensures code quality:
- Runs `npm run build` to verify production build succeeds
- Checks for TypeScript compilation errors
- Runs linting to catch code quality issues
- Verifies all dependencies are properly installed
- Confirms build artifacts are generated correctly

#### 6. Error Recovery

When builds fail, the agent analyzes and fixes errors:
- Receives build error output from backend
- Analyzes TypeScript, ESLint, and build errors
- Identifies root causes
- Implements fixes via `claude_code_execute`
- Re-runs build to verify fixes work
- Reports resolution back to user

### Integration with SAM Infrastructure

The App Agent seamlessly integrates with SAM's existing infrastructure:

**Session Management:**
- Uses standard SAM SQL-backed session service for conversation persistence
- Sessions maintain full context across multiple user interactions
- Session history includes all user messages and agent responses

**Agent Discovery:**
- Participates in SAM's agent discovery protocol
- Publishes agent card describing capabilities and skills
- Can be called by other agents or users via standard A2A protocol

**Artifact Handling:**
- Can upload/download artifacts via SAM's artifact service
- Supports file attachments in conversations
- Can reference artifacts in generated code

**Status Updates:**
- Publishes real-time progress updates via SAM event mesh
- Updates appear in UI chat as agent works
- Provides visibility into long-running code generation tasks

### Instruction Guidelines

The App Agent is configured with detailed instructions that guide its behavior:

```yaml
instruction: |
  You are an expert React developer that builds production-ready applications for the SAM platform.

  ## Your Role
  You help users create React applications that run in SAM's iframe-based app environment.
  You build apps incrementally through multi-turn conversations, showing progress after each step.

  ## Context
  - You will receive app_id, name, and description in the initial message
  - The workspace is pre-initialized with React 19 + Vite + Tailwind + SAM SDK
  - All dependencies are already installed
  - CLAUDE.md in workspace contains full SAM SDK documentation

  ## Workflow
  1. **Understand Requirements**: Ask clarifying questions about features, data sources, UI/UX
  2. **Propose Plan**: Outline components, pages, SAM agent calls needed
  3. **Incremental Development**: Use claude_code_execute to build features one at a time
  4. **Iterate**: Respond to user feedback, make changes via claude_code_execute
  5. **Validate**: Before user deploys, suggest final build check

  ## SAM Integration Guidelines
  - Apps can call ANY SAM agent via SAM.agents.call(agentId, {prompt})
  - Use SAM.storage for persistence (app-scoped key-value)
  - Use SAM.artifacts for file handling
  - Always initialize SDK: await SAM.ready()

  ## Code Quality Standards
  - Use TypeScript for type safety
  - Use Tailwind for ALL styling
  - Make apps responsive (mobile + desktop)
  - Handle errors gracefully
  - Follow React best practices
```

These instructions ensure consistent, high-quality app development across all user interactions.

### Comparison to Original Design

The agent-based architecture provides several advantages over the original UI-managed approach:

| Aspect | Original Design | Agent-Based Design |
|--------|----------------|-------------------|
| **Code Generation Control** | UI directly calls claude-code, manages execution | App Agent orchestrates claude-code autonomously |
| **User Interaction** | Imperative commands to coding tool | Conversational dialogue with intelligent agent |
| **Requirements** | User must specify complete requirements upfront | Agent elicits requirements through questions |
| **Error Handling** | UI presents errors, user manually triggers retry | Agent receives errors, analyzes, and fixes automatically |
| **Workflow Flexibility** | Fixed workflow in UI code | Agent adapts workflow based on user needs |
| **Complexity Location** | UI components manage coding workflow | Agent encapsulates complexity, UI stays simple |
| **Scalability** | UI code grows with new features | Agent instructions updated, UI unchanged |
| **Separation of Concerns** | UI = presentation + orchestration | UI = presentation only, Agent = orchestration |

---

## SAM SDK Design

### Package Structure

```
client/webui/sam-sdk/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── README.md
├── src/
│   ├── index.ts                 # Main entry, exports SAM object
│   ├── core/
│   │   ├── SamSDK.ts            # Main SDK class
│   │   ├── transport.ts         # postMessage initialization
│   │   └── config.ts            # SDK configuration
│   ├── modules/
│   │   ├── auth.ts              # Authentication module
│   │   ├── agents.ts            # Agent calling
│   │   ├── llm.ts               # Direct LLM access
│   │   ├── artifacts.ts         # Artifact CRUD
│   │   ├── tasks.ts             # Task history
│   │   ├── storage.ts           # Key-value storage
│   │   ├── users.ts             # User search
│   │   ├── notifications.ts     # Toast notifications
│   │   └── ui.ts                # Theme, parent UI integration
│   ├── utils/
│   │   ├── api.ts               # authenticatedFetch wrapper
│   │   ├── events.ts            # EventEmitter
│   │   └── helpers.ts           # Utilities
│   └── types/
│       ├── index.ts             # All type exports
│       ├── sdk.ts               # SDK-specific types
│       └── api.ts               # API request/response types
├── react/                       # React-specific exports
│   ├── index.ts
│   └── hooks.ts                 # useAgent, useStorage, etc.
└── dist/                        # Build output
    ├── index.js
    ├── index.d.ts
    └── sam-sdk.css
```

### Core API

```typescript
// Import SDK
import { SAM } from '@sam/sdk';

// SDK auto-initializes via postMessage handshake
await SAM.ready(); // Promise resolves when initialized

// ===== AUTH MODULE =====
const user = SAM.auth.getCurrentUser();
// { userId: string, email: string, displayName: string, permissions: string[] }

SAM.auth.onAuthChange((user) => {
  if (!user) {
    // Handle logout
  }
});

// ===== AGENT MODULE =====
// Simple agent call
const result = await SAM.agents.call('data-analyzer', {
  prompt: 'Analyze sales data',
  context: { timeframe: 'last-30-days' }
});

// Streaming agent call
const stream = SAM.agents.stream('report-generator', {
  prompt: 'Generate quarterly report'
});

stream.on('status', (status) => {
  console.log('Status:', status.message);
});

stream.on('text', (chunk) => {
  appendToUI(chunk);
});

stream.on('artifact', (artifact) => {
  console.log('Created:', artifact.filename);
});

stream.on('complete', (result) => {
  console.log('Done!', result);
});

stream.on('error', (error) => {
  handleError(error);
});

// ===== LLM MODULE =====
// Direct Claude access
const response = await SAM.llm.complete({
  prompt: 'Summarize this data',
  model: 'claude-sonnet-4',
  maxTokens: 1000
});

// Streaming LLM
const llmStream = SAM.llm.stream({
  messages: [
    { role: 'user', content: 'Write a poem' }
  ]
});

llmStream.on('text', (chunk) => { /* ... */ });

// ===== ARTIFACTS MODULE =====
// Upload
const artifact = await SAM.artifacts.upload(file, {
  description: 'User data CSV'
});

// Download
const blob = await SAM.artifacts.download(artifactId);
const url = URL.createObjectURL(blob);

// List
const artifacts = await SAM.artifacts.list({
  type: 'image/*',
  limit: 20
});

// Delete
await SAM.artifacts.delete(artifactId);

// ===== STORAGE MODULE =====
// Get/Set (app-scoped automatically)
await SAM.storage.set('user-preferences', {
  theme: 'dark',
  layout: 'grid'
});

const prefs = await SAM.storage.get('user-preferences');

// List keys
const keys = await SAM.storage.keys();

// Bulk operations
await SAM.storage.setMany({
  'key1': 'value1',
  'key2': { complex: 'object' }
});

const data = await SAM.storage.getMany(['key1', 'key2']);

// ===== TASKS MODULE =====
// List tasks
const tasks = await SAM.tasks.list({
  status: 'completed',
  limit: 20
});

// Get task
const task = await SAM.tasks.get(taskId);

// ===== USERS MODULE =====
// Search users
const users = await SAM.users.search('john');

// ===== UI MODULE =====
// Get theme
const theme = SAM.ui.getTheme(); // 'light' | 'dark'

// Listen for theme changes
SAM.ui.onThemeChange((theme) => {
  applyTheme(theme);
});

// Show notification in parent
SAM.ui.showNotification({
  title: 'Success',
  message: 'Data saved',
  type: 'success'
});

// Open artifact in parent UI
SAM.ui.openArtifact(artifactId);
```

### React Hooks

```typescript
import { useAgent, useStorage, useArtifacts, useTheme } from '@sam/sdk/react';

function MyDashboard() {
  // Agent calling hook
  const { call, loading, result, error } = useAgent('data-analyzer');

  // Storage hook (like useState but persisted)
  const [preferences, setPreferences] = useStorage('user-prefs', {
    theme: 'dark',
    refreshInterval: 5000
  });

  // Artifacts hook
  const { artifacts, loading: artifactsLoading, refetch } = useArtifacts();

  // Theme hook
  const { theme, setTheme } = useTheme();

  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      <button onClick={() => call({ prompt: 'Analyze data' })}>
        Analyze
      </button>
      {loading && <Spinner />}
      {result && <ResultView data={result} />}
    </div>
  );
}
```

---

## Backend Infrastructure

### Existing Endpoints (SDK Can Use)

From `src/solace_agent_mesh/gateway/http_sse/routers/`:

#### tasks.py
- `POST /message:stream` - Agent calling with SSE
- `POST /message:send` - Non-streaming agent call
- `GET /tasks` - List all tasks
- `GET /tasks/{task_id}` - Get task details
- `GET /tasks/{task_id}/events` - Get task events
- `POST /tasks/{taskId}:cancel` - Cancel task

#### artifacts.py
- `POST /artifacts/upload` - Upload artifact (FormData)
- `GET /artifacts/{session_id}` - List artifacts
- `GET /artifacts/{session_id}/download/{filename}` - Download
- `DELETE /artifacts/{session_id}/{filename}` - Delete

#### sessions.py
- `GET /sessions` - List sessions
- `GET /sessions/search` - Search sessions
- `GET /sessions/{session_id}` - Get session

#### agent_cards.py
- `GET /agentCards` - List available agents

#### users.py
- `GET /me` - Current user info
- `GET /me/capabilities` - User capabilities

#### people.py
- `GET /people/search` - Search users

#### auth.py
- `POST /auth/refresh` - Refresh access token

### New Endpoints Required

#### 1. Apps Router (`routers/apps.py`)

The Apps Router manages app CRUD operations, workspace lifecycle, dev server containers, and deployment.

**Create New App:**
```python
@router.post("/apps")
async def create_app(
    request: CreateAppRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """
    Create new app with workspace from Docker template.

    1. Insert into apps table (app_id, user_id, name, description, status='draft')
    2. Create workspace: /workspaces/{user_id}/apps/{app_id}/
    3. Copy pre-built template from claude-code-sam-app Docker image
    4. Update package.json with app name
    5. Initialize git repository
    6. Generate CLAUDE.md with app context + SAM SDK docs
    7. Return app_id and workspace_path
    """
    app_id = request.name.lower().replace(" ", "-")
    workspace_path = f"/var/sam/workspaces/{user_id}/apps/{app_id}"

    # Create DB record
    app_repository.create(db, app_id, user_id, request.name, request.description)

    # Create workspace from Docker template
    # This is done by backend, NOT by claude-code or UI
    create_workspace_from_template(workspace_path, app_id, request.name)

    return {
        "app_id": app_id,
        "workspace_path": workspace_path,
        "status": "draft"
    }
```

**List User Apps:**
```python
@router.get("/apps")
async def list_apps(
    page_number: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """List all apps for user with pagination"""
    return app_repository.list_user_apps(db, user_id, page_number, page_size)
```

**Get App Details:**
```python
@router.get("/apps/{app_id}")
async def get_app(
    app_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Get app metadata and current version"""
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app
```

**Update App Metadata:**
```python
@router.patch("/apps/{app_id}")
async def update_app(
    app_id: str,
    request: UpdateAppRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Update app name or description"""
    return app_repository.update(db, app_id, user_id, request.name, request.description)
```

**Deploy New Version:**
```python
@router.post("/apps/{app_id}/deploy")
async def deploy_app(
    app_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """
    Deploy new version of app:
    1. Run npm run build in container
    2. Validate build output
    3. Create new version directory
    4. Update current symlink
    5. Return version info or errors

    If build fails, return errors for agent to fix.
    """
    app = app_repository.get_by_id(db, app_id, user_id)
    workspace_path = app.workspace_path

    # Run build in container
    build_result = run_build_in_container(workspace_path)

    if build_result.success:
        # Create new version
        version_num = app.current_version + 1
        version_dir = f"/var/sam/workspaces/{user_id}/apps-deployed/{app_id}/v{version_num}"

        # Copy dist/ to version directory
        shutil.copytree(f"{workspace_path}/dist", version_dir)

        # Update current symlink
        current_link = f"/var/sam/workspaces/{user_id}/apps-deployed/{app_id}/current"
        if os.path.islink(current_link):
            os.unlink(current_link)
        os.symlink(f"v{version_num}", current_link)

        # Update DB
        app_repository.update_version(db, app_id, version_num)

        # Stop dev server if running
        if app_id in _dev_server_containers:
            stop_dev_server(app_id, user_id)

        return {"success": True, "version": version_num}
    else:
        # Return errors for agent to fix
        return {"success": False, "errors": build_result.errors}
```

**Dev Server Proxy (HTTP):**
```python
@router.get("/apps/preview/{app_id}/{path:path}")
async def proxy_dev_server(
    app_id: str,
    path: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """
    Proxy HTTP requests to containerized Vite dev server.
    Starts dev server container if not already running.
    """
    # Verify user owns app
    app = app_repository.get_by_id(db, app_id, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Start dev server if not running
    if app_id not in _dev_server_containers:
        start_dev_server(app_id, app.workspace_path, user_id)

    # Proxy to container's internal URL
    container_info = _dev_server_containers[app_id]
    internal_url = container_info["internal_url"]

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{internal_url}/{path}")
        return Response(
            content=response.content,
            media_type=response.headers.get('content-type')
        )
```

**Dev Server Proxy (WebSocket for HMR):**
```python
@router.websocket("/apps/preview/{app_id}/__vite_hmr")
async def proxy_hmr_websocket(
    websocket: WebSocket,
    app_id: str,
    db: Session = Depends(get_db)
):
    """
    Bidirectional WebSocket proxy for Vite Hot Module Replacement.
    Enables instant updates in preview pane when agent modifies code.
    """
    await websocket.accept()

    # Get container info
    if app_id not in _dev_server_containers:
        await websocket.close()
        return

    container_info = _dev_server_containers[app_id]
    internal_url = container_info["internal_url"].replace("http://", "ws://")

    # Bidirectional proxy
    async with websockets.connect(f"{internal_url}/__vite_hmr") as vite_ws:
        async def forward_to_vite():
            while True:
                data = await websocket.receive_text()
                await vite_ws.send(data)

        async def forward_to_client():
            async for message in vite_ws:
                await websocket.send_text(message)

        await asyncio.gather(forward_to_vite(), forward_to_client())
```

**Archive App:**
```python
@router.delete("/apps/{app_id}")
async def archive_app(
    app_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    """Soft delete app (mark as archived)"""
    app_repository.archive(db, app_id, user_id)

    # Stop dev server if running
    if app_id in _dev_server_containers:
        stop_dev_server(app_id, user_id)

    return {"status": "archived"}
```

**Dev Server Container Management:**

The backend manages ephemeral Vite dev server containers for live preview with hot reload.

```python
# Track running dev server containers
# {app_id: {container_id, internal_url, user_id, started_at}}
_dev_server_containers = {}

def start_dev_server(app_id: str, workspace_path: str, user_id: str) -> str:
    """
    Start containerized Vite dev server on internal Docker network.
    Returns internal URL for proxying.
    """
    container_runtime = detect_container_runtime()
    container_name = f"vite-dev-{app_id}"

    # Start container on internal network (NOT exposed to internet)
    docker_cmd = [
        container_runtime, "run", "-d",
        "--name", container_name,
        "--network", "sam-internal",  # Internal network only
        "-v", f"{workspace_path}:/workspace:Z",
        "--memory", "512m",
        "--cpus", "1",
        "--user", "node",
        "vite-dev-server:latest"
    ]

    result = subprocess.run(docker_cmd, capture_output=True, text=True)
    container_id = result.stdout.strip()

    # Get container's internal IP on sam-internal network
    inspect_cmd = [
        container_runtime, "inspect", "-f",
        "{{.NetworkSettings.Networks.sam-internal.IPAddress}}",
        container_id
    ]
    ip_result = subprocess.run(inspect_cmd, capture_output=True, text=True)
    container_ip = ip_result.stdout.strip()

    internal_url = f"http://{container_ip}:5173"

    # Track container
    _dev_server_containers[app_id] = {
        "container_id": container_id,
        "internal_url": internal_url,
        "user_id": user_id,
        "started_at": time.time()
    }

    return internal_url

def stop_dev_server(app_id: str, user_id: str):
    """Stop and remove dev server container"""
    if app_id not in _dev_server_containers:
        return

    container_info = _dev_server_containers[app_id]
    if container_info["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    container_runtime = detect_container_runtime()
    subprocess.run([container_runtime, "stop", container_info["container_id"]])
    subprocess.run([container_runtime, "rm", container_info["container_id"]])

    del _dev_server_containers[app_id]

# Background task to cleanup stale containers
async def cleanup_stale_dev_servers():
    """Auto-cleanup containers idle for > 1 hour"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        now = time.time()
        stale = [
            app_id
            for app_id, info in _dev_server_containers.items()
            if now - info["started_at"] > 3600  # 1 hour
        ]
        for app_id in stale:
            try:
                stop_dev_server(app_id, info["user_id"])
            except Exception as e:
                logger.error(f"Failed to cleanup container {app_id}: {e}")
```

**Key Design Points:**

- **Workspace Creation**: Backend creates workspaces by copying from Docker template, NOT via claude-code
- **Agent Involvement**: App Agent only uses claude-code tools to write code in existing workspace
- **Containerized Dev Servers**: Vite runs in Docker containers on internal network for security
- **Hot Reload**: WebSocket proxy enables instant preview updates when agent modifies files
- **Build Validation**: Deploy endpoint runs build, returns errors to agent for fixing if build fails
- **Resource Limits**: Dev server containers limited to 512MB RAM, 1 CPU
- **Auto-Cleanup**: Stale containers cleaned up after 1 hour of inactivity

#### 2. Storage Router (`routers/storage.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from ..shared.auth_utils import get_current_user

router = APIRouter(prefix="/storage", tags=["Storage"])

@router.get("/{app_id}/{key}")
async def get_value(
    app_id: str,
    key: str,
    user_id: str = Depends(get_current_user)
):
    """Get value from app storage"""
    # Query: SELECT value FROM storage WHERE user_id=? AND app_id=? AND key=?
    pass

@router.post("/{app_id}/{key}")
async def set_value(
    app_id: str,
    key: str,
    value: dict,
    user_id: str = Depends(get_current_user)
):
    """Set value in app storage"""
    # INSERT OR UPDATE storage
    pass

@router.delete("/{app_id}/{key}")
async def delete_value(
    app_id: str,
    key: str,
    user_id: str = Depends(get_current_user)
):
    """Delete value from app storage"""
    pass

@router.get("/{app_id}/keys")
async def list_keys(
    app_id: str,
    user_id: str = Depends(get_current_user)
):
    """List all keys in app storage"""
    pass

@router.post("/{app_id}:batch-get")
async def batch_get(
    app_id: str,
    keys: list[str],
    user_id: str = Depends(get_current_user)
):
    """Get multiple values at once"""
    pass

@router.post("/{app_id}:batch-set")
async def batch_set(
    app_id: str,
    data: dict[str, any],
    user_id: str = Depends(get_current_user)
):
    """Set multiple values at once"""
    pass
```

**Database Schema:**

```sql
CREATE TABLE storage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    app_id VARCHAR(255) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(user_id, app_id, key)
);

CREATE INDEX idx_storage_lookup ON storage(user_id, app_id, key);
CREATE INDEX idx_storage_app ON storage(user_id, app_id);
```

#### 2. LLM Router (`routers/llm.py`)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..shared.auth_utils import get_current_user

router = APIRouter(prefix="/llm", tags=["LLM"])

@router.post("/complete")
async def complete(
    request: LLMCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """Direct LLM completion (non-streaming)"""
    # Use SAM's existing LLM provider
    # Apply user rate limits
    # Return completion
    pass

@router.post("/stream")
async def stream(
    request: LLMCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """Streaming LLM completion (SSE)"""
    # Use SAM's existing LLM provider
    # Stream via EventSource
    async def generate():
        async for chunk in llm_provider.stream(request):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

**Request/Response Types:**

```python
class LLMCompletionRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[list[Message]] = None
    model: Optional[str] = "claude-sonnet-4"
    max_tokens: Optional[int] = 4000
    temperature: Optional[float] = 1.0

class LLMCompletionResponse(BaseModel):
    text: str
    model: str
    usage: TokenUsage
```

---

## Frontend Integration

### Apps Navigation

Add new routes to SAM UI router:

```typescript
// client/webui/frontend/src/main.tsx or routes config

const router = createBrowserRouter([
  // ... existing routes
  {
    path: "/apps",
    element: <AppsPage />,
  },
  {
    path: "/apps/new",
    element: <CreateAppPage />,
  },
  {
    path: "/apps/:appId/edit",
    element: <CreateAppPage />,
  },
  {
    path: "/apps/:appId",
    element: <AppViewPage />,
  },
  {
    path: "/apps/preview/:workspaceId",
    element: <AppPreviewPage />, // Standalone preview for dev server
  },
]);
```

### Apps List Page

```typescript
// client/webui/frontend/src/pages/AppsPage.tsx

export function AppsPage() {
  const { apps, loading } = useApps(); // Custom hook
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">My Apps</h1>
        <Button onClick={() => navigate('/apps/new')}>
          New App
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {apps.map(app => (
          <AppCard
            key={app.id}
            app={app}
            onClick={() => navigate(`/apps/${app.id}`)}
          />
        ))}
      </div>
    </div>
  );
}
```

### App Frame Component

```typescript
// client/webui/frontend/src/components/apps/AppFrame.tsx

interface AppFrameProps {
  appId: string;
  workspacePath: string;
}

export function AppFrame({ appId, workspacePath }: AppFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { user } = useAuthContext();
  const { theme } = useThemeContext();
  const { configServerUrl } = useConfigContext();

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Wait for iframe to load
    iframe.onload = () => {
      // Send initialization message
      iframe.contentWindow?.postMessage({
        type: 'init',
        authToken: getAccessToken(),
        apiEndpoint: `${configServerUrl}/api/v1`,
        user: {
          id: user.userId,
          email: user.email,
          displayName: user.displayName
        },
        theme: theme,
        appId: appId
      }, '*'); // TODO: Restrict origin
    };

    // Listen for messages from app
    const handleMessage = (event: MessageEvent) => {
      // Validate origin
      if (event.source !== iframe.contentWindow) return;

      const { type, payload } = event.data;

      switch (type) {
        case 'ready':
          console.log('App ready');
          break;
        case 'notification':
          showNotification(payload);
          break;
        case 'openArtifact':
          // Navigate to artifact view
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [appId, user, theme]);

  return (
    <iframe
      ref={iframeRef}
      src={`/apps/${appId}/index.html`}
      sandbox="allow-scripts allow-same-origin"
      className="w-full h-full border-0"
      title={`App: ${appId}`}
    />
  );
}
```

### Backend Dev Server Support (Containerized)

To enable hot reload during app creation, the webui gateway manages ephemeral Vite dev server containers with mounted workspaces. This approach works in cloud/VPC environments.

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/apps.py` (NEW)

```python
from fastapi import APIRouter, Depends, HTTPException
from ..shared.auth_utils import get_current_user
from ...agent.tools.claude_code.utils import detect_container_runtime
import subprocess
import time

router = APIRouter(prefix="/apps", tags=["Apps"])

# Track running dev server containers: {workspace_id: {container_id, internal_url, user_id, started_at}}
_dev_server_containers = {}

@router.post("/dev-server")
async def start_dev_server(
    request: DevServerRequest,
    user_id: str = Depends(get_current_user)
):
    """Start Vite dev server in ephemeral container"""
    workspace_id = request.workspaceId
    workspace_path = request.workspacePath

    # Check if container already running
    if workspace_id in _dev_server_containers:
        return {"devServerUrl": f"/api/v1/apps/preview/{workspace_id}"}

    # Start Vite dev server in container
    container_runtime = detect_container_runtime()
    container_name = f"vite-dev-{workspace_id}"

    docker_cmd = [
        container_runtime, "run", "-d",  # Detached mode
        "--name", container_name,
        "--network", "sam-internal",  # Internal network only
        "-v", f"{workspace_path}:/workspace:Z",  # Mount workspace
        "--memory", "512m",  # Resource limits
        "--cpus", "1",
        "--user", "node",
        "vite-dev-server:latest",
    ]

    result = subprocess.run(docker_cmd, capture_output=True, text=True)
    container_id = result.stdout.strip()

    # Get container's internal IP
    inspect_cmd = [
        container_runtime, "inspect", "-f",
        "{{.NetworkSettings.Networks.sam-internal.IPAddress}}",
        container_id
    ]
    ip_result = subprocess.run(inspect_cmd, capture_output=True, text=True)
    container_ip = ip_result.stdout.strip()

    internal_url = f"http://{container_ip}:5173"

    # Track container
    _dev_server_containers[workspace_id] = {
        "container_id": container_id,
        "internal_url": internal_url,
        "user_id": user_id,
        "started_at": time.time(),
    }

    return {"devServerUrl": f"/api/v1/apps/preview/{workspace_id}"}

@router.delete("/dev-server/{workspace_id}")
async def stop_dev_server(
    workspace_id: str,
    user_id: str = Depends(get_current_user)
):
    """Stop Vite dev server container"""
    if workspace_id not in _dev_server_containers:
        raise HTTPException(status_code=404, detail="Dev server not found")

    container_info = _dev_server_containers[workspace_id]
    if container_info["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    container_runtime = detect_container_runtime()

    # Stop and remove container
    subprocess.run([container_runtime, "stop", container_info["container_id"]])
    subprocess.run([container_runtime, "rm", container_info["container_id"]])

    del _dev_server_containers[workspace_id]

    return {"status": "stopped"}

@router.post("/")
async def create_app(
    request: CreateAppRequest,
    user_id: str = Depends(get_current_user)
):
    """Save and deploy app"""
    # Stop dev server container if running
    if request.workspaceId in _dev_server_containers:
        await stop_dev_server(request.workspaceId, user_id)

    # Save app metadata to database
    # ... (implementation details)

    return {"appId": request.workspaceId}

# Background task to cleanup stale containers
async def cleanup_stale_dev_servers():
    """Auto-cleanup containers idle for > 1 hour"""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        now = time.time()
        stale = [
            workspace_id
            for workspace_id, info in _dev_server_containers.items()
            if now - info["started_at"] > 3600  # 1 hour
        ]
        for workspace_id in stale:
            try:
                await stop_dev_server(workspace_id, info["user_id"])
            except Exception as e:
                logger.error(f"Failed to cleanup container {workspace_id}: {e}")
```

**Vite Dev Server Docker Image:**

**File:** `docker/vite-dev-server/Dockerfile`

```dockerfile
FROM node:20-slim

# Install Vite globally
RUN npm install -g vite

WORKDIR /workspace

# Expose port 5173 (internal network only)
EXPOSE 5173

# Run Vite dev server on all interfaces (internal network)
CMD ["vite", "--host", "0.0.0.0", "--port", "5173"]
```

**Build image:**
```bash
cd docker/vite-dev-server
docker build -t vite-dev-server:latest .
```

**Security Considerations:**

- Containers run on internal Docker network only (NOT exposed to internet)
- No external port exposure
- Resource limits prevent abuse (512MB RAM, 1 CPU)
- Auto-cleanup after 1 hour of inactivity
- User isolation via auth checks
- Works in cloud/VPC environments (no localhost dependency)

---

## Claude Code Integration

### Agent-Based Code Generation

In the agent-based architecture, **the App Agent uses claude-code tools** to generate code and manage the workspace. The UI does not directly interact with claude-code.

**Key Workflow:**

1. **Backend Creates Workspace**: When user creates app via UI, backend creates workspace by copying pre-built template from Docker image
2. **UI Creates Session**: UI automatically creates session with App Agent
3. **Agent Uses Claude Code Tools**: App Agent calls `claude_code_execute` tool to write code, run builds, and manage files
4. **Streaming Updates**: Agent's progress updates (file edits, builds, etc.) stream to UI chat via SAM event mesh
5. **Preview Available**: Once agent runs successful build, UI enables preview pane

**Important Distinctions:**

| Component | Role | Uses Claude Code? |
|-----------|------|-------------------|
| **UI** | Presents chat interface, shows preview | ❌ No - only creates sessions |
| **App Agent** | Orchestrates development, asks questions, writes code | ✅ Yes - via claude_code_execute tool |
| **Backend** | Creates workspaces, manages dev servers, validates builds | ❌ No - manages infrastructure only |

This separation ensures:
- UI remains simple (just session management + preview)
- Agent has full control over code generation workflow
- Backend handles infrastructure (workspaces, containers, builds)

### Workspace Configuration

Apps are created as claude-code workspaces with `workspace_type: "app"`:

```yaml
workspace_id: "user-{userId}-app-{appName}"
workspace_type: "app"
environment: "sam-app"  # Uses specialized image
workspace_name: "{App Name}"
workspace_description: "{User's description}"
```

### Specialized Docker Image: `claude-code-sam-app`

#### Rationale

SAM apps require a consistent, specific tech stack (React 19 + Vite + Tailwind + @sam/sdk) that differs from general Node.js development. A specialized Docker image dramatically improves the app creation experience:

**Benefits:**
- **Instant setup**: Pre-installed dependencies eliminate 5+ minute npm install on first turn
- **Better UX**: "Create app" feels fast and responsive
- **Consistent environment**: Every app uses same baseline versions
- **Optimized for purpose**: Tuned specifically for React + SAM stack
- **Reduced agent work**: Claude Code doesn't need to manage dependency installation

**Trade-offs:**
- Larger image size (~1-2GB vs ~500MB)
- Requires rebuilds when dependencies update
- Less flexible for non-standard stacks (acceptable for SAM apps)

#### Container Architecture

**File:** `docker/claude-code-sam-app/Dockerfile`

```dockerfile
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user
RUN useradd -m -s /bin/bash samapp

# Create directories
RUN mkdir -p /workspace /home/samapp/.claude /opt/app-template && \
    chown -R samapp:samapp /workspace /home/samapp/.claude /opt/app-template

# Switch to non-root user
USER samapp
WORKDIR /opt/app-template

# Configure git
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

# ===== PRE-BUILT APP TEMPLATE =====
# This template workspace is copied to new app workspaces for instant setup

# Create package.json with all dependencies
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/package.json ./package.json

# Install all dependencies (cached in image)
RUN npm install

# Copy configuration files
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/tsconfig.json ./tsconfig.json
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/vite.config.ts ./vite.config.ts
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/tailwind.config.ts ./tailwind.config.ts
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/postcss.config.js ./postcss.config.js
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/.eslintrc.json ./.eslintrc.json
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/.gitignore ./.gitignore

# Copy starter source files
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/src ./src
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/public ./public
COPY --chown=samapp:samapp docker/claude-code-sam-app/template/index.html ./index.html

# Pre-build the template to verify everything works
RUN npm run build

WORKDIR /workspace
ENTRYPOINT ["claude"]
```

#### Template Package.json

**File:** `docker/claude-code-sam-app/template/package.json`

```json
{
  "name": "sam-app-template",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@sam/sdk": "^1.0.0",
    "plotly.js": "^2.27.0",
    "react-plotly.js": "^2.6.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.300.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@types/plotly.js": "^2.29.0",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.16",
    "eslint": "^8.55.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.32",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.8.0",
    "vite": "^6.0.0"
  }
}
```

#### Template Structure

```
docker/claude-code-sam-app/template/
├── package.json              # Dependencies listed above
├── tsconfig.json             # TypeScript config (strict mode)
├── vite.config.ts            # Vite config with React plugin
├── tailwind.config.ts        # Tailwind CSS config
├── postcss.config.js         # PostCSS with Tailwind
├── .eslintrc.json           # ESLint config
├── .gitignore               # Standard React .gitignore
├── index.html               # Entry HTML
├── public/                  # Static assets
│   └── vite.svg            # Vite logo
└── src/
    ├── main.tsx            # React root with SAM SDK init
    ├── App.tsx             # Minimal starter component
    ├── App.css             # Basic styles
    └── index.css           # Tailwind imports
```

**File:** `docker/claude-code-sam-app/template/src/main.tsx`

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { SAM } from '@sam/sdk'

// Initialize SAM SDK
SAM.ready().then(() => {
  console.log('SAM SDK initialized');

  // Render app
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}).catch((error) => {
  console.error('Failed to initialize SAM SDK:', error);
});
```

**File:** `docker/claude-code-sam-app/template/src/App.tsx`

```typescript
import { useState } from 'react'
import { SAM } from '@sam/sdk'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-2xl mx-auto bg-white dark:bg-gray-800 rounded-lg shadow-xl p-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            SAM App Template
          </h1>
          <p className="text-gray-600 dark:text-gray-300 mb-8">
            This is a starter template. Tell Claude Code what you want to build!
          </p>

          <div className="space-y-4">
            <button
              onClick={() => setCount((count) => count + 1)}
              className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Count is {count}
            </button>

            <div className="text-sm text-gray-500 dark:text-gray-400">
              <p>✓ React 19 with TypeScript</p>
              <p>✓ Tailwind CSS for styling</p>
              <p>✓ SAM SDK ready to use</p>
              <p>✓ Hot reload enabled</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
```

#### Workspace Initialization with Template

When claude-code creates an app workspace, it copies the pre-built template:

**Modified:** `src/solace_agent_mesh/agent/tools/claude_code/execute_tool.py`

```python
async def _initialize_workspace(
    self,
    workspace_path: Path,
    environment: str,
    workspace_name: str,
    workspace_description: str,
) -> None:
    """Initialize workspace with template for sam-app environment"""

    if environment == "sam-app":
        # Copy pre-built template from container
        # Template is at /opt/app-template in the container
        # This is handled by mounting the template directory

        # Generate package.json with app-specific name
        package_json = {
            "name": workspace_name.lower().replace(" ", "-"),
            "private": True,
            "version": "0.0.0",
            "type": "module",
            # ... rest copied from template
        }

        package_json_path = workspace_path / "package.json"
        package_json_path.write_text(json.dumps(package_json, indent=2))

        # Template already has node_modules, src/, config files
        # Just need to update CLAUDE.md
    else:
        # Existing initialization for other environments
        pass

    # Create CLAUDE.md (all environments)
    claude_md_content = generate_claude_md(
        workspace_name, workspace_description, environment
    )
    claude_md_path = workspace_path / "CLAUDE.md"
    claude_md_path.write_text(claude_md_content)

    # Initialize git repository
    await asyncio.create_subprocess_exec("git", "init", cwd=str(workspace_path))
    # ... rest of git setup
```

**Container Execution with Template Mount:**

```python
# In run_claude_code_headless()
if environment == "sam-app":
    # Mount template directory to pre-populate workspace
    docker_cmd.extend([
        "-v", "/opt/app-template:/template:ro,Z",  # Read-only template
    ])

    # On first execution, copy template to workspace if empty
    # This happens inside container via entrypoint script
```

#### Version Management Strategy

**Dependency Versions:**
- Pin major versions: React 19.x, Vite 6.x, TypeScript 5.8.x
- Allow minor/patch updates within major version
- SAM SDK pinned to specific version (updated when SDK releases)

**Image Versioning:**
```bash
# Tag images with date and SAM SDK version
docker build -t claude-code-sam-app:latest .
docker tag claude-code-sam-app:latest claude-code-sam-app:2024-12-06
docker tag claude-code-sam-app:latest claude-code-sam-app:sdk-1.0.0
```

**Rebuild Triggers:**
- Weekly automated rebuild (picks up patch updates)
- Manual rebuild when @sam/sdk publishes new version
- Manual rebuild for security patches
- CI/CD pipeline validates build succeeds

#### Performance Comparison

**Without specialized image (general node):**
```
Turn 1: "Create app"
  - npm init: 5 seconds
  - npm install: 180-300 seconds (3-5 minutes)
  - First build: 15 seconds
  Total: ~5-6 minutes before preview available
```

**With specialized image (sam-app template):**
```
Turn 1: "Create app"
  - Copy template: 2 seconds (in container)
  - Update package.json: <1 second
  - First build: 10 seconds (cached node_modules)
  Total: ~12-15 seconds before preview available
```

**Result: 20-30x faster app creation** ⚡

#### Container Image Map

Update container runtime to recognize `sam-app` environment:

**File:** `src/solace_agent_mesh/agent/tools/claude_code/utils.py`

```python
container_user_map = {
    "node": {"user": "node", "home": "/home/node", "image": "claude-code-node:latest"},
    "python": {"user": "python", "home": "/home/python", "image": "claude-code-python:latest"},
    "go": {"user": "go", "home": "/home/go", "image": "claude-code-go:latest"},
    "sam-app": {"user": "samapp", "home": "/home/samapp", "image": "claude-code-sam-app:latest"},
}
```

### CLAUDE.md Template

Generated for each app workspace:

```markdown
# {App Name}

{User's description}

## Environment

This is a React + TypeScript + Vite + Tailwind application that will run in the SAM platform.

## Available Tools & Libraries

Pre-installed npm packages:
- react@19
- react-dom@19
- typescript@5.8
- vite@6
- tailwindcss@4
- @sam/sdk (SAM platform integration)
- plotly.js (data visualization)
- recharts (charts)
- lucide-react (icons)
- clsx, tailwind-merge

## SAM SDK

The `@sam/sdk` package provides integration with the SAM platform:

```typescript
import { SAM } from '@sam/sdk';

// Call agents
const result = await SAM.agents.call('agent-name', { prompt: '...' });

// Access LLM
const response = await SAM.llm.complete({ prompt: '...' });

// Manage artifacts
const artifact = await SAM.artifacts.upload(file);

// Persist data (app-scoped)
await SAM.storage.set('key', value);
const data = await SAM.storage.get('key');
```

See full SDK documentation at the end of this file.

## Requirements

- Build must succeed: `npm run build`
- Linting must pass: `npm run lint`
- TypeScript must compile without errors
- App must be responsive (mobile + desktop)
- Follow React best practices (hooks, composition)

## Development Process

1. Set up project structure
2. Install dependencies
3. Create components
4. Implement features using SAM SDK
5. Test build and lint
6. Verify functionality

---

## SAM SDK Full Reference

[Full API documentation here - same as earlier in this doc]
```

### Agent Instructions

The coding agent should receive these instructions:

```
You are building a React application that will run in the SAM platform.

CRITICAL REQUIREMENTS:
- Use TypeScript for all code
- Use Tailwind CSS for styling
- Follow React 19 patterns (hooks, composition)
- Use @sam/sdk for all SAM platform integration
- Run `npm run build` and `npm run lint` before finishing
- Ensure app is responsive

AVAILABLE via @sam/sdk:
- SAM.agents.call() - Call SAM agents
- SAM.llm.complete() - Direct LLM access
- SAM.artifacts.upload() - Upload files
- SAM.storage.set()/get() - Persist app data

WORKFLOW:
1. Create project structure (src/, public/, etc.)
2. Set up Vite config, tsconfig, tailwind config
3. Install dependencies
4. Build React components
5. Integrate with SAM SDK
6. Test: npm run build && npm run lint
7. Verify: Test in development mode

DO NOT:
- Ask for approval to run builds or tests
- Create unnecessary abstractions
- Add features not requested
- Skip build validation
```

---

## App Lifecycle Management

### Overview

SAM apps have a complete lifecycle from creation through deployment, updates, and archiving. This section details each stage, file organization, and state transitions.

### Lifecycle States

```
┌─────────────┐
│  Creation   │  User creates new app via chat interface
│  (Dev Mode) │  Files in: /workspaces/{user}/apps/{workspace_id}/
└──────┬──────┘  Vite dev server running (proxied)
       │
       ↓
┌─────────────┐
│   Editing   │  User modifies app via chat
│  (Dev Mode) │  Changes appear in live preview via HMR
└──────┬──────┘  Can edit indefinitely before deploying
       │
       ↓ "Save & Deploy"
┌─────────────┐
│  Deployed   │  Production build in: /workspaces/{user}/apps-deployed/{app_id}/v{N}/
│ (Published) │  App accessible at /apps/{app_id}
└──────┬──────┘  Dev server stopped
       │
       ├─────→ "Edit" ────────────────┐
       │                              ↓
       │                    ┌─────────────┐
       │                    │ Re-editing  │  Dev server restarts
       │                    │  (Dev Mode) │  Work on existing app
       │                    └──────┬──────┘
       │                           │
       │                           ↓ "Save & Deploy"
       │                    ┌─────────────┐
       │                    │  Deployed   │  New version (v{N+1})
       │                    │   (v{N+1})  │  Old versions preserved
       │                    └─────────────┘
       │
       ↓ "Archive"
┌─────────────┐
│  Archived   │  Status: archived in database
│             │  Files remain, app hidden from UI
└─────────────┘  Can be restored
```

### File Structure

All app-related files live under the workspaces directory:

```
/var/sam/workspaces/
├── {user}/
│   ├── apps/                           # Development workspaces
│   │   └── {workspace_id}/
│   │       ├── src/
│   │       ├── public/
│   │       ├── dist/                   # Local build output
│   │       ├── node_modules/
│   │       ├── package.json
│   │       ├── tsconfig.json
│   │       ├── vite.config.ts
│   │       ├── CLAUDE.md
│   │       └── .git/
│   │
│   ├── apps-deployed/                  # Production deployments
│   │   └── {app_id}/
│   │       ├── v1/                     # Version 1 (timestamp: 1701234567)
│   │       │   ├── index.html
│   │       │   ├── assets/
│   │       │   │   ├── index-abc123.js
│   │       │   │   └── index-def456.css
│   │       │   └── metadata.json
│   │       ├── v2/                     # Version 2 (timestamp: 1701345678)
│   │       ├── current -> v2           # Symlink to active version
│   │       └── versions.json           # Version history
│   │
│   └── sessions/                       # Temporary workspaces (non-apps)
│
└── default_user/                       # Claude Code settings (tool config)
    └── ...
```

**Design Decisions:**
- Everything under `/workspaces/` for single storage location
- `apps/` for development, `apps-deployed/` for production
- Versioned deployments with `current` symlink
- No separate settings folder (use tool configuration)

### State 1: Creation Mode (Development)

**User Action:** Click "New App" → Navigate to `/apps/new`

**UI State:**
- Full page with chat interface (left) + preview pane (right)
- Preview initially hidden (shown after first successful build)
- App name input, "Save & Deploy" button (disabled until build succeeds)

**Backend Actions:**
1. Create workspace directory:
   ```
   /var/sam/workspaces/{user}/apps/{workspace_id}/
   ```

2. Copy template from Docker image:
   ```bash
   cp -r /opt/app-template/* /workspace/
   ```

3. Initialize git repository:
   ```bash
   cd /workspace
   git init
   git add .
   git commit -m "Initial commit from template"
   ```

4. Create session with app-builder agent

**Dev Server (First Build):**
When agent runs first build (`npm run build`), backend starts Vite dev server in a containerized environment:

```python
# Start dev server in ephemeral Docker container
# This approach works in cloud/VPC deployments where "localhost" is not viable

container_runtime = detect_container_runtime()  # docker or podman
container_name = f"vite-dev-{workspace_id}"

# Run Vite dev server in lightweight container
docker_cmd = [
    container_runtime, "run", "-d",  # Detached mode
    "--name", container_name,
    "--network", "sam-internal",  # Internal Docker network (NOT exposed to internet)
    "-v", f"{workspace_path}:/workspace:Z",  # Mount workspace
    "--memory", "512m",  # Resource limits
    "--cpus", "1",
    "--user", "node",  # Non-root user
    "vite-dev-server:latest",  # Lightweight Vite container image
]

result = subprocess.run(docker_cmd, capture_output=True, text=True)
container_id = result.stdout.strip()

# Get container's internal IP on sam-internal network
inspect_cmd = [
    container_runtime, "inspect", "-f",
    "{{.NetworkSettings.Networks.sam-internal.IPAddress}}",
    container_id
]
ip_result = subprocess.run(inspect_cmd, capture_output=True, text=True)
container_ip = ip_result.stdout.strip()

internal_url = f"http://{container_ip}:5173"

# Track server
_dev_server_containers[workspace_id] = {
    "container_id": container_id,
    "internal_url": internal_url,
    "user_id": user_id,
    "started_at": time.time(),
}
```

**Dev Server Security:**
- Runs in isolated Docker container (not on host system)
- Container on internal Docker network only (NO external port exposure)
- NOT accessible from internet
- Only accessible via webui gateway proxy on internal network
- Works in cloud/VPC deployments (no "localhost" dependency)

**Frontend Access:**
```typescript
// Iframe points to SAM backend, NOT localhost
<iframe src={`/api/v1/apps/preview/${workspaceId}/index.html`} />
```

**Backend Proxy (Webui Gateway):**
```python
@router.get("/apps/preview/{workspace_id}/{path:path}")
async def proxy_dev_server(
    workspace_id: str,
    path: str,
    user_id: str = Depends(get_current_user)
):
    """Proxy to Vite dev server container on internal network"""

    # Verify user owns this workspace
    container_info = _dev_server_containers.get(workspace_id)
    if not container_info or container_info['user_id'] != user_id:
        raise HTTPException(404)

    internal_url = container_info['internal_url']

    # Proxy to container's internal URL (e.g., http://172.18.0.5:5173)
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{internal_url}/{path}")
        return Response(
            content=response.content,
            media_type=response.headers.get('content-type'),
        )

@router.websocket("/apps/preview/{workspace_id}/__vite_hmr")
async def proxy_hmr_websocket(websocket: WebSocket, workspace_id: str):
    """Proxy Vite HMR WebSocket for hot reload"""
    await websocket.accept()

    container_info = _dev_server_containers.get(workspace_id)
    if not container_info:
        await websocket.close()
        return

    internal_url = container_info['internal_url'].replace('http://', 'ws://')

    # Bidirectional proxy to container's WebSocket (e.g., ws://172.18.0.5:5173)
    async with websockets.connect(f"{internal_url}/__vite_hmr") as vite_ws:
        async def forward_to_vite():
            while True:
                data = await websocket.receive_text()
                await vite_ws.send(data)

        async def forward_to_client():
            async for message in vite_ws:
                await websocket.send_text(message)

        await asyncio.gather(forward_to_vite(), forward_to_client())
```

**Hot Reload Flow:**
```
1. Agent modifies src/App.tsx in workspace
2. Vite (in container) detects file change via mounted workspace
3. Vite sends HMR update via WebSocket to container's internal IP
4. WebSocket proxied through SAM backend/gateway to browser
5. Browser receives update from proxy
6. React Fast Refresh updates component
7. User sees change instantly (no reload)
```

**Key Benefits of Containerized Dev Servers:**
- Works in cloud/VPC environments (AWS, GCP, Azure)
- No "localhost" dependency on backend pods
- Container isolation provides security
- Resource limits prevent runaway processes
- Scales horizontally (each user gets own container)
- Easy cleanup (just delete container)

**Workspace State:**
- Status: `in_development`
- Has dev server: Yes
- Has production build: No

### State 2: Edit Mode (Development)

**User Action:** Click "Edit" on deployed app → Navigate to `/apps/{appId}/edit`

**Backend Actions:**
1. Check if workspace exists:
   ```
   /var/sam/workspaces/{user}/apps/{workspace_id}/
   ```

2. If workspace was deleted:
   - Option A: Restore from latest git version (if we kept .git)
   - Option B: Show dialog: "Workspace deleted. Create from deployed version?"
   - If user confirms: Copy deployed app back to workspace

3. Start dev server (same as creation mode)

4. Resume or create new session with app-builder agent

**UI State:**
- Same full page interface as creation
- Preview shows current app state
- Chat continues from previous conversation (if session exists)

**Workspace State:**
- Status: `in_development` (even though app is deployed)
- Has dev server: Yes
- Has production build: Yes (previous deployments remain)

### State 3: Deployment (Build & Publish)

**User Action:** Click "Save & Deploy"

**Deployment Flow:**

```python
async def deploy_app(workspace_id: str, app_name: str, user_id: str):
    workspace_path = f"/var/sam/workspaces/{user_id}/apps/{workspace_id}"

    # 1. Run production build
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=workspace_path,
        capture_output=True
    )
    if result.returncode != 0:
        raise Exception("Build failed")

    # 2. Determine version number
    app_id = app_name.lower().replace(" ", "-")
    deployed_base = f"/var/sam/workspaces/{user_id}/apps-deployed/{app_id}"

    # Get next version number
    if os.path.exists(deployed_base):
        versions = [d for d in os.listdir(deployed_base) if d.startswith('v')]
        version_num = len(versions) + 1
    else:
        version_num = 1

    version_dir = f"{deployed_base}/v{version_num}"
    os.makedirs(version_dir, exist_ok=True)

    # 3. Copy dist/ to version directory
    shutil.copytree(
        f"{workspace_path}/dist",
        version_dir,
        dirs_exist_ok=True
    )

    # 4. Get git commit SHA
    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace_path
    ).decode().strip()

    # 5. Create version metadata
    metadata = {
        "version": version_num,
        "deployed_at": int(time.time()),
        "git_commit": git_sha,
        "app_name": app_name,
    }
    with open(f"{version_dir}/metadata.json", "w") as f:
        json.dump(metadata, f)

    # 6. Update "current" symlink
    current_link = f"{deployed_base}/current"
    if os.path.islink(current_link):
        os.unlink(current_link)
    os.symlink(f"v{version_num}", current_link)

    # 7. Create git tag in workspace
    subprocess.run(
        ["git", "tag", f"v{version_num}"],
        cwd=workspace_path
    )

    # 8. Update database
    await db.execute(
        """
        INSERT INTO apps (app_id, user_id, name, current_version, workspace_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(app_id) DO UPDATE SET
            current_version = ?,
            updated_at = ?
        """,
        (app_id, user_id, app_name, version_num, workspace_id, now, now, version_num, now)
    )

    await db.execute(
        """
        INSERT INTO app_versions (version_id, app_id, version_number, deployed_at, build_path, git_commit)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (f"{app_id}-v{version_num}", app_id, version_num, now, version_dir, git_sha)
    )

    # 9. Stop dev server
    if workspace_id in _dev_servers:
        _dev_servers[workspace_id]['process'].terminate()
        del _dev_servers[workspace_id]

    return {
        "app_id": app_id,
        "version": version_num,
        "deployed_at": now,
    }
```

**Result:**
- New version directory created
- Production build copied
- Symlink updated
- Database updated
- Dev server stopped
- User redirected to `/apps/{app_id}`

### State 4: Production Running

**User Action:** Navigate to `/apps/{appId}` or click app from apps list

**UI State:**
- Full-screen iframe showing deployed app
- No chat interface
- No dev server
- "Edit" button to re-enter development mode

**Serving Production App:**

```python
@router.get("/apps/{app_id}/app/{path:path}")
async def serve_production_app(
    app_id: str,
    path: str,
    user_id: str = Depends(get_current_user)
):
    """Serve production app files from deployed version"""

    # Verify user owns app
    app = await db.fetch_one(
        "SELECT * FROM apps WHERE app_id = ? AND user_id = ? AND status != 'archived'",
        (app_id, user_id)
    )
    if not app:
        raise HTTPException(404)

    # Serve from "current" symlink
    file_path = f"/var/sam/workspaces/{user_id}/apps-deployed/{app_id}/current/{path}"

    if not os.path.exists(file_path):
        raise HTTPException(404)

    return FileResponse(file_path)
```

**Frontend:**
```typescript
<iframe src={`/api/v1/apps/${appId}/app/index.html`} />
```

**Workspace State:**
- Status: `deployed`
- Has dev server: No
- Has production build: Yes
- Current version: v{N}

### State 5: Enhancement (Back to Development)

**Same as Edit Mode** - user clicks "Edit", re-enters development mode.

**On subsequent "Save & Deploy":**
- Creates v{N+1}
- Old versions (v1, v2, ..., vN) remain available
- Symlink updates to v{N+1}
- Database records new version

### State 6: Archive

**User Action:** Click "Archive" on app

**Backend Actions:**

```python
@router.post("/apps/{app_id}/archive")
async def archive_app(app_id: str, user_id: str = Depends(get_current_user)):
    """Soft-delete app (mark as archived)"""

    await db.execute(
        "UPDATE apps SET status = 'archived', archived_at = ? WHERE app_id = ? AND user_id = ?",
        (int(time.time()), app_id, user_id)
    )

    # Stop dev server if running
    workspace_id = await get_workspace_id_for_app(app_id, user_id)
    if workspace_id in _dev_servers:
        _dev_servers[workspace_id]['process'].terminate()
        del _dev_servers[workspace_id]

    return {"status": "archived"}
```

**Result:**
- App hidden from apps list in UI
- All files remain on disk (workspace + deployed versions)
- Can be restored later

**Restore:**
```python
@router.post("/apps/{app_id}/restore")
async def restore_app(app_id: str, user_id: str = Depends(get_current_user)):
    """Un-archive app"""
    await db.execute(
        "UPDATE apps SET status = 'deployed', archived_at = NULL WHERE app_id = ? AND user_id = ?",
        (app_id, user_id)
    )
    return {"status": "deployed"}
```

### Version Management

**Rollback to Previous Version:**

```python
@router.post("/apps/{app_id}/rollback/{version}")
async def rollback_version(app_id: str, version: int, user_id: str = Depends(get_current_user)):
    """Rollback to previous version"""

    deployed_base = f"/var/sam/workspaces/{user_id}/apps-deployed/{app_id}"
    version_dir = f"{deployed_base}/v{version}"

    if not os.path.exists(version_dir):
        raise HTTPException(404, "Version not found")

    # Update "current" symlink
    current_link = f"{deployed_base}/current"
    if os.path.islink(current_link):
        os.unlink(current_link)
    os.symlink(f"v{version}", current_link)

    # Update database
    await db.execute(
        "UPDATE apps SET current_version = ? WHERE app_id = ?",
        (version, app_id)
    )

    return {"current_version": version}
```

**UI:**
- App settings page shows version history
- User can select version and click "Rollback"
- Rollback is instant (just updates symlink)

### Export Anytime

**User Action:** Click "Export" on app (available in any state)

**Backend:**

```python
@router.get("/apps/{app_id}/export")
async def export_app(app_id: str, user_id: str = Depends(get_current_user)):
    """Export app as .tar.gz"""

    workspace_path = f"/var/sam/workspaces/{user_id}/apps/{workspace_id}"
    export_path = f"/tmp/{app_id}-export.tar.gz"

    # Create tarball of workspace
    subprocess.run(
        ["tar", "-czf", export_path, "-C", workspace_path, "."],
        check=True
    )

    return FileResponse(
        export_path,
        filename=f"{app_id}.tar.gz",
        media_type="application/gzip"
    )
```

**Export includes:**
- All source code
- Git history
- Configuration files
- node_modules excluded (can npm install after import)

### Copy/Clone for Sharing

**Instead of sharing apps, users can copy:**

```python
@router.post("/apps/{app_id}/clone")
async def clone_app(app_id: str, new_name: str, user_id: str = Depends(get_current_user)):
    """Create a copy of app for current user"""

    # Get original app
    original = await db.fetch_one(
        "SELECT * FROM apps WHERE app_id = ? AND (user_id = ? OR is_public = true)",
        (app_id, user_id)
    )

    # Copy workspace
    original_workspace = f"/var/sam/workspaces/{original.user_id}/apps/{original.workspace_id}"
    new_workspace_id = f"clone-{app_id}-{int(time.time())}"
    new_workspace = f"/var/sam/workspaces/{user_id}/apps/{new_workspace_id}"

    shutil.copytree(original_workspace, new_workspace)

    # Update package.json with new name
    # ...

    # Create new app record
    new_app_id = new_name.lower().replace(" ", "-")
    await db.execute(
        "INSERT INTO apps (app_id, user_id, name, workspace_id, ...) VALUES (...)",
        (new_app_id, user_id, new_name, new_workspace_id, ...)
    )

    return {"app_id": new_app_id}
```

---

## Security Model

### iframe Sandboxing

```html
<iframe
  sandbox="allow-scripts allow-same-origin"
  src="/apps/{appId}/index.html"
/>
```

**Sandbox restrictions:**
- `allow-scripts`: Required for React
- `allow-same-origin`: Allows API calls to SAM backend
- NO `allow-top-navigation`: Prevents escaping iframe
- NO `allow-popups`: Blocks popup windows
- NO `allow-forms`: Prevents form submissions outside API

### Content Security Policy

Apps should have restricted CSP:

```http
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  connect-src https://{SAM_DOMAIN};
  img-src 'self' data: https:;
  font-src 'self';
```

### postMessage Origin Validation

SDK validates origin:

```typescript
window.addEventListener('message', (event) => {
  // Only accept messages from SAM parent
  if (event.origin !== window.location.ancestorOrigins[0]) {
    return;
  }

  // Process message
});
```

Parent validates origin:

```typescript
const handleMessage = (event: MessageEvent) => {
  // Only accept from our iframe
  if (event.source !== iframeRef.current?.contentWindow) {
    return;
  }

  // Process message
};
```

### Authentication

- Parent never sends refresh token to iframe
- Access token passed once via postMessage on init
- SDK stores token in memory (not localStorage)
- Token expires with parent session
- SDK cannot access cookies or local storage

### Storage Isolation

- Each app gets its own storage namespace
- Storage keyed by `(user_id, app_id, key)`
- Apps cannot access other apps' data
- Apps cannot access global user storage
- Enforced at database level

### Rate Limiting

- Apps use user's existing quotas
- LLM calls count toward user limits
- Agent calls count toward user limits
- No per-app limits (yet)

---

## Implementation Roadmap

### Phase 0: App Agent Configuration (Week 0)

**Goal:** Define App Agent that orchestrates all app building

- [ ] Create App Agent YAML configuration (`examples/agents/app-agent.yaml`)
- [ ] Configure claude-code tools for agent
- [ ] Define agent instruction with React development workflow
- [ ] Configure session service for persistent conversations
- [ ] Define agent card with skills (requirements elicitation, architecture design, code generation, etc.)
- [ ] Test agent can call claude_code_execute tool
- [ ] Verify agent responds conversationally to app building requests

**Deliverables:**
- Working App Agent accessible via SAM
- Agent can converse and gather requirements
- Agent can use claude_code_execute to generate code
- Documentation of agent capabilities

**Critical Design Points:**
- App Agent orchestrates ALL code generation (not UI)
- Agent uses claude-code tools autonomously
- Agent asks clarifying questions before building
- Agent builds incrementally with user feedback

### Phase 1: Backend Infrastructure (Week 1-2)

**Goal:** Create backend endpoints for apps, storage, dev servers, and deployment

- [ ] Create apps router (`routers/apps.py`)
- [ ] Create apps repository (`repository/app_repository.py`)
- [ ] Create apps model (`repository/models/app_model.py`)
- [ ] Create database migration for apps and app_versions tables
- [ ] Implement apps CRUD endpoints (create, list, get, update, archive)
- [ ] Implement workspace creation from Docker template (backend copies template, NOT claude-code)
- [ ] Implement dev server container management (start, stop, cleanup)
- [ ] Implement HTTP proxy to dev server containers
- [ ] Implement WebSocket proxy for Vite HMR
- [ ] Implement deployment endpoint with build validation
- [ ] Create storage router (`routers/storage.py`)
- [ ] Create storage repository (`repository/storage_repository.py`)
- [ ] Create storage model (`repository/models/storage_model.py`)
- [ ] Create database migration for storage table
- [ ] Implement storage endpoints (get, set, delete, keys, batch)
- [ ] Add tests for apps router
- [ ] Add tests for storage router
- [ ] Update main.py to include new routers

**Deliverables:**
- Working `/apps/*` endpoints for app CRUD and deployment
- Containerized dev server management (cloud-ready)
- Working `/storage/*` endpoints for app-scoped storage
- Tests passing
- Documentation

**Critical Design Points:**
- Backend creates workspaces from Docker template (NOT via claude-code)
- Dev servers run in ephemeral containers on internal network
- Build validation returns errors to agent for fixing
- All infrastructure managed by backend, agent only writes code

### Phase 2: SDK Core (Week 2-3)

**Goal:** Build TypeScript SDK package

- [ ] Create package structure (`client/webui/sam-sdk/`)
- [ ] Set up build tooling (Vite, TypeScript)
- [ ] Implement transport layer (postMessage)
- [ ] Implement auth module
- [ ] Implement API utilities (authenticatedFetch)
- [ ] Implement agents module (call, stream)
- [ ] Implement artifacts module
- [ ] Implement storage module
- [ ] Implement LLM module
- [ ] Implement tasks module
- [ ] Implement users module
- [ ] Implement UI module
- [ ] Create React hooks package
- [ ] Write unit tests
- [ ] Write API documentation

**Deliverables:**
- `@sam/sdk` npm package
- `@sam/sdk/react` hooks
- Full TypeScript types
- API documentation
- Unit tests

### Phase 3: Frontend Integration (Week 3-4)

**Goal:** Add Apps section to SAM UI with session-based chat interface and preview

- [ ] Create `/apps` route (apps list page)
- [ ] Create `/apps/new` route (form to create app, then navigate to edit)
- [ ] Create `/apps/:appId/edit` route (full page with chat + preview)
- [ ] Create `/apps/:appId` route (view deployed app in iframe)
- [ ] Create AppsPage component (apps list/grid)
- [ ] Create AppCard component
- [ ] Create CreateAppPage component (simple form for name + description)
- [ ] Create AppEditorPage component (chat interface + preview pane)
- [ ] Reuse ChatMessageList and ChatInput from existing chat UI
- [ ] Create AppPreviewFrame component (iframe loading from dev server proxy)
- [ ] Create AppFrame component (for deployed apps)
- [ ] Create useApps hook (fetch apps list from backend)
- [ ] Implement app creation flow (POST /apps → auto-create session → auto-send initial message)
- [ ] Implement session management with App Agent (using existing session API)
- [ ] Implement preview toggle (show/hide preview pane based on build status)
- [ ] Add Apps to main navigation
- [ ] Implement postMessage handshake (parent ↔ iframe)
- [ ] Implement theme propagation (SAM theme → iframe app)
- [ ] Implement build error feedback dialog (show errors, "Send to Agent" button)
- [ ] Add app versioning UI
- [ ] Write integration tests

**Deliverables:**
- Working Apps UI in SAM
- Form-based app creation (name + description)
- Session-based chat interface with App Agent (reuses existing chat components)
- Auto-session creation and initial message on app create
- Live preview pane (toggleable, loads from backend proxy)
- App viewing in iframe for deployed apps
- postMessage communication for SAM SDK initialization
- Build error feedback loop (errors → dialog → inject to agent chat)
- Tests passing

**Critical Design Points:**
- UI does NOT manage claude-code directly
- UI only creates sessions with App Agent
- Chat interface reuses existing SAM chat components
- Preview pane loads from backend dev server proxy
- All code generation happens via App Agent using claude-code tools

### Phase 4: Claude Code Integration (Week 4-5)

**Goal:** Enable AI to build apps via claude-code with specialized container

- [ ] Create `docker/claude-code-sam-app/` directory structure
- [ ] Create Dockerfile for sam-app image
- [ ] Create template directory (`docker/claude-code-sam-app/template/`)
- [ ] Create template package.json with all dependencies
- [ ] Create template config files (tsconfig, vite.config, tailwind.config)
- [ ] Create template starter app (main.tsx, App.tsx with SAM SDK)
- [ ] Build and test sam-app container image
- [ ] Update execute_tool.py to support sam-app environment
- [ ] Implement template copying for workspace initialization
- [ ] Update container_user_map with sam-app configuration
- [ ] Create CLAUDE.md template generator for sam-app
- [ ] Verify App Agent configuration works with sam-app environment (agent config created in Phase 0)
- [ ] Add build validation checks
- [ ] Add linting checks
- [ ] Test full app creation flow with specialized image
- [ ] Verify 20-30x performance improvement
- [ ] Document app development workflow
- [ ] Set up CI/CD for weekly image rebuilds

**Deliverables:**
- `claude-code-sam-app:latest` Docker image
- Pre-built template with all dependencies
- @sam/sdk pre-installed and ready to use
- CLAUDE.md with full SDK docs
- Working end-to-end app creation (12-15 seconds vs 5-6 minutes)
- App Agent ready to use with specialized image
- Sample apps demonstrating SAM SDK features

### Phase 5: Polish & Documentation (Week 5-6)

**Goal:** Production-ready feature

- [ ] Performance optimization
- [ ] Security audit
- [ ] Error handling improvements
- [ ] Loading states and feedback
- [ ] User documentation
- [ ] Developer documentation
- [ ] Example apps gallery
- [ ] Video tutorial
- [ ] Release notes

**Deliverables:**
- Production-ready feature
- Complete documentation
- Example apps
- Tutorial content

---

## API Reference

### SAM SDK API

See [SAM SDK Design](#sam-sdk-design) section above for complete API reference.

### Backend Endpoints

#### Storage API

```
GET    /storage/{app_id}/{key}           - Get value
POST   /storage/{app_id}/{key}           - Set value
DELETE /storage/{app_id}/{key}           - Delete value
GET    /storage/{app_id}/keys            - List keys
POST   /storage/{app_id}:batch-get       - Bulk get
POST   /storage/{app_id}:batch-set       - Bulk set
```

#### LLM API

```
POST   /llm/complete                     - Non-streaming completion
POST   /llm/stream                       - Streaming completion (SSE)
```

---

## Examples

### Example 1: Dashboard App

```typescript
import { SAM } from '@sam/sdk';
import { useAgent, useStorage } from '@sam/sdk/react';
import { BarChart, Bar, XAxis, YAxis } from 'recharts';

function Dashboard() {
  const [config, setConfig] = useStorage('dashboard-config', {
    refreshInterval: 60000,
    agentName: 'data-analyzer'
  });

  const { call, loading, result } = useAgent(config.agentName);

  useEffect(() => {
    const interval = setInterval(() => {
      call({ prompt: 'Get latest metrics' });
    }, config.refreshInterval);

    return () => clearInterval(interval);
  }, [config.refreshInterval]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Sales Dashboard</h1>

      {loading && <Spinner />}

      {result?.data && (
        <BarChart width={600} height={300} data={result.data}>
          <Bar dataKey="sales" fill="#8884d8" />
          <XAxis dataKey="month" />
          <YAxis />
        </BarChart>
      )}
    </div>
  );
}
```

### Example 2: Data Export Tool

```typescript
import { SAM } from '@sam/sdk';
import { useState } from 'react';

function DataExporter() {
  const [format, setFormat] = useState<'csv' | 'json'>('csv');

  const handleExport = async () => {
    // Call agent to generate report
    const result = await SAM.agents.call('report-generator', {
      prompt: `Generate sales report in ${format} format`
    });

    // Download artifact
    if (result.artifacts?.length > 0) {
      const blob = await SAM.artifacts.download(result.artifacts[0].id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report.${format}`;
      a.click();
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Export Data</h1>

      <select value={format} onChange={(e) => setFormat(e.target.value)}>
        <option value="csv">CSV</option>
        <option value="json">JSON</option>
      </select>

      <button onClick={handleExport} className="ml-4 btn-primary">
        Generate & Download
      </button>
    </div>
  );
}
```

### Example 3: Chat Interface

```typescript
import { SAM } from '@sam/sdk';
import { useState } from 'react';

function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    // Stream response from agent
    const stream = SAM.agents.stream('assistant', {
      prompt: input
    });

    let assistantMsg = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMsg]);

    stream.on('text', (chunk) => {
      assistantMsg.content += chunk;
      setMessages(prev => [...prev.slice(0, -1), { ...assistantMsg }]);
    });
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-auto p-4">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'text-right' : ''}>
            <div className="inline-block p-3 rounded bg-gray-100">
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          className="w-full p-2 border rounded"
        />
      </div>
    </div>
  );
}
```

---

## Success Criteria

- [ ] SDK can be imported and initialized in iframe app
- [ ] Authentication works seamlessly (inherited from parent)
- [ ] Agent calls work with streaming callbacks
- [ ] Artifact upload/download works
- [ ] Storage persistence works (per-app isolated)
- [ ] Theme detection and updates work
- [ ] React hooks provide idiomatic integration
- [ ] TypeScript provides full type safety
- [ ] Documentation is clear and complete
- [ ] Sample app can be generated by claude-code
- [ ] Apps run securely in sandboxed iframes
- [ ] Hot reload works during development
- [ ] Build validation prevents broken apps

---

## Appendix

### Technologies Used

**Frontend:**
- React 19
- TypeScript 5.8
- Vite 6
- Tailwind CSS 4
- Radix UI (existing SAM components)

**Backend:**
- FastAPI (Python)
- PostgreSQL (existing SAM database)
- SQLAlchemy (ORM)
- Alembic (migrations)

**Development:**
- Claude Code CLI
- Docker/Podman containers
- Git (version control)
- npm/pnpm (package management)

### References

- [Claude Code Tools Documentation](./developing/claude-code-tools-dev-guide.md)
- [SAM Chat Application](../client/webui/frontend/)
- [A2A Protocol](https://github.com/solace-ai/a2a-protocol)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Vite](https://vite.dev)

---

**Document Version:** 1.2
**Last Updated:** December 7, 2024
**Status:** Planning Complete - Cloud-Ready Architecture

## Changelog

### Version 1.2 (December 7, 2024)
- **CRITICAL: Redesigned dev server architecture for cloud/VPC deployments**
  - Replaced localhost-based dev servers with containerized approach
  - Dev servers now run in ephemeral Docker containers with mounted workspaces
  - Containers on internal Docker network (sam-internal) - NO external exposure
  - Backend/gateway proxies HTTP and WebSocket traffic to containers
  - Works in cloud environments (AWS, GCP, Azure) without "localhost" dependency
  - Added resource limits (512MB RAM, 1 CPU per container)
  - Auto-cleanup of stale containers after 1 hour inactivity
- **Added new Vite dev server Docker image**
  - Lightweight image (node:20-slim + Vite)
  - Runs on container's internal IP (e.g., http://172.18.0.5:5173)
  - Dockerfile specification included
- **Updated all dev server code examples**
  - Backend proxy uses container internal URLs instead of localhost
  - WebSocket proxy for HMR updated for container networking
  - Security considerations updated for containerized approach
- **Updated hot reload flow documentation**
  - Clarified file change detection via mounted workspace
  - WebSocket proxy path through backend to browser
  - Benefits of containerized approach documented

### Version 1.1 (December 6, 2024)
- Added comprehensive "App Creation UI Architecture" section
- Documented full page design with chat interface and live preview pane
- Added CreateAppPage, useAppCreationChat, and AppPreviewFrame component specifications
- Documented Vite dev server integration for hot reload
- Added app-builder agent configuration with incremental development workflow
- Updated user experience flow to show iterative development with live preview
- Added backend dev server management endpoints
- **Added specialized Docker image: `claude-code-sam-app`**
  - Complete Dockerfile specification with pre-built template
  - Template workspace with all dependencies pre-installed
  - 20-30x faster app creation (12-15 seconds vs 5-6 minutes)
  - Pre-configured React 19 + Vite + Tailwind + SAM SDK
  - Starter app template with SAM SDK integration example
  - Version management and rebuild strategy
- **Added comprehensive "App Lifecycle Management" section**
  - Complete lifecycle: Creation → Edit → Deploy → Enhancement → Archive
  - Detailed file structure under `/workspaces/` directory
  - Dev server security architecture (localhost-only with backend proxy)
  - WebSocket proxy for Vite HMR (hot module replacement)
  - Deployment flow with versioning (v1, v2, ..., current symlink)
  - Rollback support to previous versions
  - Export anytime as .tar.gz
  - Clone/copy model for sharing apps
  - Database schema for apps and app_versions tables
- Updated implementation roadmap to include specialized image tasks
- Documented component reuse from existing chat application

### Version 1.0 (December 6, 2024)
- Initial architecture document
- Core SAM SDK design
- Backend infrastructure (storage, LLM endpoints)
- Frontend integration patterns
- Security model
- Implementation roadmap
