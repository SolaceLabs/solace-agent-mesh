import type { Meta, StoryObj } from "@storybook/react-vite";
import { SharedSessionPage } from "@/lib/components/pages/SharedSessionPage";
import { http, HttpResponse } from "msw";
import type { SharedSessionView } from "@/lib/types/share";

// Mock shared session data
const mockSharedSession: SharedSessionView = {
    share_id: "mock-share-123",
    session_id: "session-456",
    title: "Python Script Development",
    access_type: "authenticated",
    created_time: Date.now() / 1000 - 86400, // 1 day ago
    is_owner: false,
    tasks: [
        {
            id: "task-1",
            session_id: "session-456",
            user_id: "alice@example.com",
            created_time: Date.now() / 1000 - 86400,
            workflow_task_id: "workflow-task-1",
            message_bubbles: [
                {
                    id: "msg-1",
                    type: "user",
                    text: "Hi! Can you help me create a Python script to process CSV files?",
                    parts: [{ kind: "text", text: "Hi! Can you help me create a Python script to process CSV files?" }],
                    sender_display_name: "Alice Johnson",
                    sender_email: "alice@example.com",
                },
                {
                    id: "msg-2",
                    type: "agent",
                    text: "I'd be happy to help! I'll create a script that reads CSV files, processes the data, and generates reports.",
                    parts: [{ kind: "text", text: "I'd be happy to help! I'll create a script that reads CSV files, processes the data, and generates reports." }],
                },
            ],
            task_metadata: null,
        },
        {
            id: "task-2",
            session_id: "session-456",
            user_id: "alice@example.com",
            created_time: Date.now() / 1000 - 86000,
            workflow_task_id: "workflow-task-2",
            message_bubbles: [
                {
                    id: "msg-3",
                    type: "user",
                    text: "Great! Can you also add error handling for missing columns?",
                    parts: [{ kind: "text", text: "Great! Can you also add error handling for missing columns?" }],
                    sender_display_name: "Alice Johnson",
                    sender_email: "alice@example.com",
                },
                {
                    id: "msg-4",
                    type: "agent",
                    text: "I've created a Python script with comprehensive error handling for missing columns.",
                    parts: [
                        { kind: "text", text: "I've created a Python script with comprehensive error handling for missing columns." },
                        {
                            kind: "file",
                            file: {
                                name: "csv_processor.py",
                                mimeType: "text/x-python",
                                uri: "file:///csv_processor.py",
                            },
                        },
                    ],
                },
            ],
            task_metadata: null,
        },
    ],
    task_events: null,
    artifacts: [
        {
            filename: "csv_processor.py",
            mime_type: "text/x-python",
            size: 2400,
            last_modified: new Date(Date.now() - 86000 * 1000).toISOString(),
            description: "Python script for CSV processing with error handling",
        },
    ],
};

const mockSharedSessionAsOwner: SharedSessionView = {
    ...mockSharedSession,
    is_owner: true,
};

const handlers = [
    http.get("*/api/v1/share/:shareId", ({ params }) => {
        const { shareId } = params;
        if (shareId === "owner-share-123") {
            return HttpResponse.json(mockSharedSessionAsOwner);
        }
        return HttpResponse.json(mockSharedSession);
    }),
    http.post("*/api/v1/share/:shareId/fork", () => {
        return HttpResponse.json({ success: true });
    }),
];

const meta = {
    title: "Pages/Share/SharedSessionPage",
    component: SharedSessionPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Public view of a shared chat session - displays outside the main app layout with a standalone header and read-only chat content.",
            },
        },
        msw: { handlers },
    },
    args: {
        routerValues: {
            initialPath: "/share/mock-share-123",
            routePath: "/share/:shareId",
        },
    },
} satisfies Meta<typeof SharedSessionPage>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default view - user is a viewer (not the owner)
 * Shows the floating "Continue in New Chat" button
 */
export const Default: Story = {};

/**
 * View as owner - shows "Go to Chat" button instead of fork button
 */
export const AsOwner: Story = {
    args: {
        routerValues: {
            initialPath: "/share/owner-share-123",
            routePath: "/share/:shareId",
        },
    },
};

/**
 * With side panel expanded to show files
 */
export const WithSidePanelExpanded: Story = {
    play: async ({ canvasElement }) => {
        // Wait for page to load
        await new Promise(resolve => setTimeout(resolve, 500));

        // Find and click the expand panel button
        const expandButton = canvasElement.querySelector('[aria-label="Expand Panel"]') as HTMLButtonElement;
        if (expandButton) {
            expandButton.click();
        }
    },
};

/**
 * Empty state - no messages
 */
export const EmptySession: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/:shareId", () => {
                    return HttpResponse.json({
                        ...mockSharedSession,
                        tasks: [],
                        artifacts: [],
                    });
                }),
            ],
        },
    },
};

/**
 * Loading state
 */
export const Loading: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/:shareId", async () => {
                    await new Promise(resolve => setTimeout(resolve, 10000));
                    return HttpResponse.json(mockSharedSession);
                }),
            ],
        },
    },
};

/**
 * Error state - failed to load
 */
export const ErrorState: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/:shareId", () => {
                    return HttpResponse.json({ error: "Session not found" }, { status: 404 });
                }),
            ],
        },
    },
};
