import type { Meta, StoryObj } from "@storybook/react-vite";
import { CollaborationInfoCards } from "@/lib/components/chat/CollaborationInfoCards";

const meta: Meta<typeof CollaborationInfoCards> = {
    title: "Chat/Collaboration/CollaborationInfoCards",
    component: CollaborationInfoCards,
    tags: ["autodocs"],
    parameters: {
        layout: "padded",
    },
    decorators: [
        Story => (
            <div style={{ maxWidth: "800px" }}>
                <Story />
            </div>
        ),
    ],
};

export default meta;

type Story = StoryObj<typeof CollaborationInfoCards>;

export const Default: Story = {
    args: {},
};
