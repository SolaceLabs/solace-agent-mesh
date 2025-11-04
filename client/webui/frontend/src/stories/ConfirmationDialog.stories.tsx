import { Button, ConfirmationDialog } from "@/lib";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/ConfirmationDialog",
    component: ConfirmationDialog,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The button component",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw", display: "flex", justifyContent: "center", alignItems: "center" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof ConfirmationDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        title: "Confirm",
        triggerText: "Open Dialog",
        message: "Are you sure you want to do this action",
        onClose: () => alert("Action cancelled"),
        onConfirm: () => alert("Action confirmed"),
    },
};

export const CustomTrigger: Story = {
    args: {
        title: "Confirm",
        trigger: <Button variant="outline"> Custom trigger</Button>,
        message: "Are you sure you want to do this action",
        onClose: () => alert("Action cancelled"),
        onConfirm: () => alert("Action confirmed"),
    },
};
