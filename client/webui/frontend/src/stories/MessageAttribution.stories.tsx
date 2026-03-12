import type { Meta, StoryObj } from "@storybook/react-vite";
import { MessageAttribution } from "@/lib/components/chat/MessageAttribution";
import { mockCollaborativeUsers } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof MessageAttribution> = {
    title: "Chat/MessageAttribution",
    component: MessageAttribution,
    tags: ["autodocs"],
    parameters: {
        layout: "padded",
    },
};

export default meta;

type Story = StoryObj<typeof MessageAttribution>;

export const UserAttribution: Story = {
    args: {
        type: "user",
        name: mockCollaborativeUsers.alice.name,
        timestamp: Date.now() - 10 * 60 * 1000,
        userIndex: 0,
    },
};

export const AgentAttribution: Story = {
    args: {
        type: "agent",
        name: "OrchestratorAgent",
        timestamp: Date.now() - 5 * 60 * 1000,
    },
};
