import type { Meta, StoryObj } from "@storybook/react-vite";
import { MessageUserAttribution } from "@/lib/components/chat/MessageUserAttribution";
import { mockCollaborativeUsers } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof MessageUserAttribution> = {
    title: "Chat/Collaboration/MessageUserAttribution",
    component: MessageUserAttribution,
    tags: ["autodocs"],
    parameters: {
        layout: "padded",
    },
};

export default meta;

type Story = StoryObj<typeof MessageUserAttribution>;

export const Default: Story = {
    args: {
        userName: mockCollaborativeUsers.alice.name,
        timestamp: Date.now() - 10 * 60 * 1000, // 10 minutes ago
        userIndex: 0,
    },
};

export const DifferentUser: Story = {
    args: {
        userName: mockCollaborativeUsers.bob.name,
        timestamp: Date.now() - 2 * 60 * 60 * 1000, // 2 hours ago
        userIndex: 1,
    },
};
