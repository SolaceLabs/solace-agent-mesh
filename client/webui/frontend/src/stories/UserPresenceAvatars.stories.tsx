import type { Meta, StoryObj } from "@storybook/react-vite";
import { UserPresenceAvatars } from "@/lib/components/chat/UserPresenceAvatars";
import { mockCollaborativeUsers } from "@/lib/mockData/collaborativeChat";

const meta: Meta<typeof UserPresenceAvatars> = {
    title: "Chat/Collaboration/UserPresenceAvatars",
    component: UserPresenceAvatars,
    tags: ["autodocs"],
    parameters: {
        layout: "centered",
    },
};

export default meta;

type Story = StoryObj<typeof UserPresenceAvatars>;

export const TwoUsers: Story = {
    args: {
        users: [
            { ...mockCollaborativeUsers.alice, isOnline: true },
            { ...mockCollaborativeUsers.bob, isOnline: true },
        ],
    },
};

export const ExcludingCurrentUser: Story = {
    args: {
        users: [mockCollaborativeUsers.alice, mockCollaborativeUsers.bob, mockCollaborativeUsers.charlie],
        currentUserId: mockCollaborativeUsers.bob.id,
    },
};

export const ManyUsers: Story = {
    args: {
        users: [
            mockCollaborativeUsers.alice,
            mockCollaborativeUsers.bob,
            mockCollaborativeUsers.charlie,
            { ...mockCollaborativeUsers.alice, id: "user-4", name: "User Four", email: "user4@example.com", isOnline: false },
            { ...mockCollaborativeUsers.bob, id: "user-5", name: "User Five", email: "user5@example.com", isOnline: false },
            { ...mockCollaborativeUsers.charlie, id: "user-6", name: "User Six", email: "user6@example.com", isOnline: true },
        ],
    },
};
