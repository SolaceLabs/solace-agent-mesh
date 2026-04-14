import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { UserPresenceAvatars } from "@/lib/components/chat/UserPresenceAvatars";
import { mockCollaborativeUsers } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof UserPresenceAvatars> = {
    title: "Chat/UserPresenceAvatars",
    component: UserPresenceAvatars,
    tags: ["autodocs"],
    parameters: {
        layout: "centered",
    },
};

export default meta;

type Story = StoryObj<typeof UserPresenceAvatars>;

export const Default: Story = {
    args: {
        users: [
            { ...mockCollaborativeUsers.alice, isOnline: true },
            { ...mockCollaborativeUsers.bob, isOnline: true },
        ],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await expect(canvas.getByText("OO")).toBeInTheDocument();
        await expect(canvas.getByText("PP")).toBeInTheDocument();
    },
};

export const ManyUsers: Story = {
    args: {
        users: [
            mockCollaborativeUsers.alice,
            mockCollaborativeUsers.bob,
            { ...mockCollaborativeUsers.charlie, isOnline: true },
            { ...mockCollaborativeUsers.alice, id: "user-4", name: "User Four", email: "user4@example.com", isOnline: true },
            { ...mockCollaborativeUsers.bob, id: "user-5", name: "User Five", email: "user5@example.com", isOnline: true },
            { ...mockCollaborativeUsers.charlie, id: "user-6", name: "User Six", email: "user6@example.com", isOnline: true },
            { ...mockCollaborativeUsers.alice, id: "user-7", name: "User Seven", email: "user7@example.com", isOnline: true },
        ],
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await expect(canvas.getByText("+2")).toBeInTheDocument();
    },
};
