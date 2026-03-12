import type { Meta, StoryObj } from "@storybook/react-vite";
import { ShareNotificationMessage } from "@/lib/components/chat/ShareNotificationMessage";
import { mockActiveCollaborativeSession } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof ShareNotificationMessage> = {
    title: "Chat/ShareNotificationMessage",
    component: ShareNotificationMessage,
    tags: ["autodocs"],
    parameters: {
        layout: "centered",
    },
};

export default meta;

type Story = StoryObj<typeof ShareNotificationMessage>;

export const SharedWithUsersAsEditor: Story = {
    args: {
        variant: "shared-with-users",
        sharedWith: mockActiveCollaborativeSession.sharedWithNames!,
        accessLevel: "editor",
        timestamp: mockActiveCollaborativeSession.sharedAt!,
    },
};

export const SharedWithUsersAsViewer: Story = {
    args: {
        variant: "shared-with-users",
        sharedWith: mockActiveCollaborativeSession.sharedWithNames!,
        accessLevel: "viewer",
        timestamp: mockActiveCollaborativeSession.sharedAt!,
    },
};

export const SharedWithMultipleUsersAsEditor: Story = {
    args: {
        variant: "shared-with-users",
        sharedWith: ["Parminder Procurement", "Charlie Chang", "David Developer"],
        accessLevel: "editor",
        timestamp: Date.now() - 2 * 60 * 60 * 1000,
    },
};

export const SharedWithManyUsers: Story = {
    args: {
        variant: "shared-with-users",
        sharedWith: ["Parminder Procurement", "Charlie Chang", "David Developer", "Emily Engineer", "Frank Finance", "Grace Governance"],
        accessLevel: "viewer",
        timestamp: Date.now() - 3 * 60 * 60 * 1000,
    },
};

export const CreatedSharingLink: Story = {
    args: {
        variant: "created-link",
        timestamp: Date.now() - 1 * 60 * 60 * 1000,
    },
};
