import type { Meta, StoryObj } from "@storybook/react-vite";
import { ShareNotificationMessage } from "@/lib/components/chat/ShareNotificationMessage";
import { mockActiveCollaborativeSession } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof ShareNotificationMessage> = {
    title: "Chat/Collaboration/ShareNotificationMessage",
    component: ShareNotificationMessage,
    tags: ["autodocs"],
    parameters: {
        layout: "centered",
    },
};

export default meta;

type Story = StoryObj<typeof ShareNotificationMessage>;

export const Default: Story = {
    args: {
        sharedBy: mockActiveCollaborativeSession.sharedByName!,
        sharedWith: mockActiveCollaborativeSession.sharedWithNames!,
        timestamp: mockActiveCollaborativeSession.sharedAt!,
    },
};

export const MultipleUsers: Story = {
    args: {
        sharedBy: "Olive Operations",
        sharedWith: ["Parminder Procurement", "Charlie Chang", "David Developer"],
        timestamp: Date.now() - 2 * 60 * 60 * 1000,
    },
};
