import type { Meta, StoryObj } from "@storybook/react-vite";
import { SharedChatsList } from "@/lib/components/chat/SharedChatsList";
import { http, HttpResponse } from "msw";
import type { SharedWithMeItem } from "@/lib/types/share";

// Mock shared chats data
const mockSharedChats: SharedWithMeItem[] = [
    {
        share_id: "share-1",
        title: "Python Script Development",
        owner_email: "alice@example.com",
        access_level: "RESOURCE_VIEWER",
        shared_at: Date.now() - 2 * 60 * 60 * 1000, // 2 hours ago
        share_url: "http://localhost:3000/share/share-1",
    },
    {
        share_id: "share-2",
        title: "API Integration Planning",
        owner_email: "bob@example.com",
        access_level: "RESOURCE_EDITOR",
        shared_at: Date.now() - 5 * 60 * 60 * 1000, // 5 hours ago
        share_url: "http://localhost:3000/share/share-2",
        session_id: "session-123", // Editor access includes session_id
    },
    {
        share_id: "share-3",
        title: "Database Schema Design",
        owner_email: "charlie@example.com",
        access_level: "RESOURCE_VIEWER",
        shared_at: Date.now() - 24 * 60 * 60 * 1000, // 1 day ago
        share_url: "http://localhost:3000/share/share-3",
    },
    {
        share_id: "share-4",
        title: "Frontend Component Library",
        owner_email: "diana@example.com",
        access_level: "RESOURCE_VIEWER",
        shared_at: Date.now() - 48 * 60 * 60 * 1000, // 2 days ago
        share_url: "http://localhost:3000/share/share-4",
    },
    {
        share_id: "share-5",
        title: "Machine Learning Model Training",
        owner_email: "eve@example.com",
        access_level: "RESOURCE_EDITOR",
        shared_at: Date.now() - 72 * 60 * 60 * 1000, // 3 days ago
        share_url: "http://localhost:3000/share/share-5",
        session_id: "session-456",
    },
];

const handlers = [
    http.get("*/api/v1/share/shared-with-me", () => {
        return HttpResponse.json(mockSharedChats);
    }),
];

const meta = {
    title: "Chat/SharedChatsList",
    component: SharedChatsList,
    parameters: {
        layout: "padded",
        docs: {
            description: {
                component: "Displays a list of chats that have been shared with the current user. Shows in the session sidebar under the user's own chat sessions.",
            },
        },
        msw: { handlers },
    },
    decorators: [
        Story => (
            <div style={{ width: "300px", backgroundColor: "var(--background)" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof SharedChatsList>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default - Shows list of shared chats with mix of viewer and editor access
 */
export const Default: Story = {
    args: {
        maxItems: 5,
    },
};

/**
 * Limited to 3 items - Shows how list looks with fewer items
 */
export const LimitedItems: Story = {
    args: {
        maxItems: 3,
    },
};

/**
 * Single shared chat
 */
export const SingleItem: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/shared-with-me", () => {
                    return HttpResponse.json([mockSharedChats[0]]);
                }),
            ],
        },
    },
};

/**
 * All editor access - All items have editor permissions
 */
export const AllEditors: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/shared-with-me", () => {
                    return HttpResponse.json(
                        mockSharedChats.map(chat => ({
                            ...chat,
                            access_level: "RESOURCE_EDITOR",
                            session_id: `session-${chat.share_id}`,
                        }))
                    );
                }),
            ],
        },
    },
};

/**
 * Empty state - No shared chats (component returns null)
 */
export const Empty: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/shared-with-me", () => {
                    return HttpResponse.json([]);
                }),
            ],
        },
    },
};

/**
 * Loading state - API call is delayed
 */
export const Loading: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/shared-with-me", async () => {
                    await new Promise(resolve => setTimeout(resolve, 10000));
                    return HttpResponse.json(mockSharedChats);
                }),
            ],
        },
    },
};

/**
 * Long titles - Tests truncation behavior
 */
export const LongTitles: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/share/shared-with-me", () => {
                    return HttpResponse.json([
                        {
                            ...mockSharedChats[0],
                            title: "This is a very long chat title that should be truncated to fit within the available space",
                        },
                        {
                            ...mockSharedChats[1],
                            title: "Another extremely long title that tests how the component handles text overflow and truncation",
                        },
                    ]);
                }),
            ],
        },
    },
};

/**
 * Interactive - Click to navigate
 */
export const Interactive: Story = {
    play: async ({ canvasElement }) => {
        // Wait for shared chats to load
        await new Promise(resolve => setTimeout(resolve, 500));

        // Find and hover over first shared chat
        const firstChat = canvasElement.querySelector("button");
        if (firstChat) {
            firstChat.dispatchEvent(new MouseEvent("mouseenter", { bubbles: true }));
        }
    },
};

/**
 * In Session Panel Context - Shows how it appears in the full session sidebar
 * with user's own sessions above the shared chats section
 */
export const InSessionPanel: Story = {
    decorators: [
        Story => (
            <div className="bg-sidebar flex h-[600px] w-[300px] flex-col">
                {/* Mock user's own sessions */}
                <div className="px-6 pt-4 pb-2">
                    <span className="text-sidebar-foreground text-sm font-bold">Your Chats</span>
                </div>
                <div className="flex-1 overflow-y-auto">
                    {/* Mock session items */}
                    <div className="flex flex-col">
                        <button className="text-sidebar-foreground hover:bg-sidebar-accent bg-sidebar-accent flex h-10 w-full cursor-pointer items-center gap-2 border-none pr-4 pl-6 text-left text-sm">
                            <span className="truncate">Current Chat Session</span>
                        </button>
                        <button className="text-sidebar-foreground hover:bg-sidebar-accent flex h-10 w-full cursor-pointer items-center gap-2 border-none pr-4 pl-6 text-left text-sm">
                            <span className="truncate">API Documentation Review</span>
                        </button>
                        <button className="text-sidebar-foreground hover:bg-sidebar-accent flex h-10 w-full cursor-pointer items-center gap-2 border-none pr-4 pl-6 text-left text-sm">
                            <span className="truncate">Bug Fix Planning</span>
                        </button>
                    </div>

                    {/* Shared chats section */}
                    <Story />
                </div>
            </div>
        ),
    ],
};
