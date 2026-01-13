import type { Meta, StoryObj } from "@storybook/react-vite";
import { ShareDialog } from "@/lib/components/projects/ShareDialog";
import type { Project } from "@/lib/types/projects";

// Mock Project Data
const mockProject: Project = {
    id: "p123",
    name: "My Awesome Agent",
    userId: "user1",
    description: "A project for testing sharing functionality",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    role: "owner",
};

const meta: Meta<typeof ShareDialog> = {
    title: "Projects/ShareDialog",
    component: ShareDialog,
    decorators: [
        Story => (
            <div className="flex justify-center bg-slate-50 p-12">
                <Story />
            </div>
        ),
    ],
};

export default meta;
type Story = StoryObj<typeof ShareDialog>;

export const Default: Story = {
    args: {
        project: mockProject,
    },
    parameters: {
        docs: {
            description: {
                story: "The ShareDialog requires a ProjectProvider context to function. This story renders the trigger button.",
            },
        },
    },
};

export const DisabledForViewer: Story = {
    args: {
        project: {
            ...mockProject,
            role: "viewer", // Viewers shouldn't see the share button
        },
    },
};
