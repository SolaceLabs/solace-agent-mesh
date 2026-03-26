import type { Meta, StoryObj } from "@storybook/react-vite";
import { http, HttpResponse } from "msw";
import { ShareDialog } from "@/lib/components/share/ShareDialog";

// Mock data
const mockShareLink = {
    share_id: "share-123",
    share_url: "https://example.com/share/abc123xyz",
    session_id: "test-session-123",
    created_time: Math.floor(Date.now() / 1000) - 86400, // Created 1 day ago
    require_authentication: true,
};

const mockOwner = {
    owner_email: "owner@example.com",
};

// Mock viewer added 2 days ago (will show as outdated for recent sessions)
const mockViewerOld = {
    user_email: "viewer@example.com",
    added_at: Math.floor(Date.now() / 1000) - 172800, // Added 2 days ago
    access_level: "read-only" as const,
};

// Mock viewer added recently (will show as up-to-date)
const mockViewerRecent = {
    user_email: "viewer@example.com",
    added_at: Math.floor(Date.now() / 1000) - 3600, // Added 1 hour ago
    access_level: "read-only" as const,
};

/** Shared args across all stories */
const sharedArgs = {
    sessionId: "test-session-123",
    sessionTitle: "My Chat Session",
    sessionUpdatedTime: new Date().toISOString(),
    open: true,
    onOpenChange: () => {},
    onError: (error: { title: string; message: string }) => console.error(error.title, error.message),
    onSuccess: (message: string) => console.log(message),
} satisfies Partial<typeof ShareDialog extends React.ComponentType<infer P> ? P : never>;

const meta: Meta<typeof ShareDialog> = {
    title: "Chat/ShareDialog",
    component: ShareDialog,
    tags: ["autodocs"],
    parameters: {
        layout: "centered",
        configContext: {
            identityServiceType: "local", // Enable user typeahead
        },
        msw: {
            handlers: [
                // Get share link - correct endpoint
                http.get("/api/v1/share/link/:sessionId", () => {
                    return HttpResponse.json(mockShareLink);
                }),
                // Get share users with 1 viewer - correct endpoint
                http.get("/api/v1/share/:shareId/users", () => {
                    return HttpResponse.json({
                        ...mockOwner,
                        users: [mockViewerRecent],
                    });
                }),
                // Add share users
                http.post("/api/v1/share/:shareId/users", () => {
                    return HttpResponse.json({ success: true });
                }),
                // Delete share users
                http.delete("/api/v1/share/:shareId/users", () => {
                    return HttpResponse.json({ success: true });
                }),
            ],
        },
    },
};

export default meta;
type Story = StoryObj<typeof ShareDialog>;

// Default state with owner and 1 viewer
export const Default: Story = {
    args: { ...sharedArgs },
};

// With add row visible
export const WithAddRow: Story = {
    args: { ...sharedArgs, defaultShowAddRow: true },
};

// With public link visible
export const WithPublicLink: Story = {
    args: { ...sharedArgs, defaultShowPublicLink: true },
};

// With both add row and public link
export const FullyExpanded: Story = {
    args: {
        ...sharedArgs,
        sessionTitle: "My Chat Session with a Very Long Title That Might Need Truncation",
        defaultShowAddRow: true,
        defaultShowPublicLink: true,
    },
};

// With outdated session (shows update snapshot button for the viewer)
export const WithOutdatedSession: Story = {
    args: {
        ...sharedArgs,
        sessionTitle: "Recently Updated Chat",
        // Session updated 1 day ago (after viewer was added 2 days ago)
        sessionUpdatedTime: new Date(Date.now() - 86400000).toISOString(),
    },
    parameters: {
        msw: {
            handlers: [
                http.get("/api/v1/share/link/:sessionId", () => {
                    return HttpResponse.json(mockShareLink);
                }),
                http.get("/api/v1/share/:shareId/users", () => {
                    return HttpResponse.json({
                        ...mockOwner,
                        users: [mockViewerOld], // Use old viewer to trigger outdated snapshot
                    });
                }),
            ],
        },
    },
};

// With no viewers (just owner)
export const OnlyOwner: Story = {
    args: { ...sharedArgs, sessionTitle: "Chat Not Shared Yet" },
    parameters: {
        msw: {
            handlers: [
                http.get("/api/v1/share/link/:sessionId", () => {
                    return HttpResponse.json(mockShareLink);
                }),
                http.get("/api/v1/share/:shareId/users", () => {
                    return HttpResponse.json({
                        ...mockOwner,
                        users: [], // No viewers
                    });
                }),
            ],
        },
    },
};

// Closed state
export const Closed: Story = {
    args: { ...sharedArgs, open: false },
};
