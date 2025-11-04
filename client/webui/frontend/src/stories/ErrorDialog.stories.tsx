import { ErrorDialog } from "@/lib";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/ErrorDialog",
    component: ErrorDialog,
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
} satisfies Meta<typeof ErrorDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        title: "Error",
        error: "Something went wrong",
        onClose: () => alert("Action cancelled"),
    },
};

export const WithErrorDetails = {
    args: {
        title: "Error",
        error: "Something went wrong",
        errorDetails: "This action is forbidden. Ensure you have the right authorization.",
        onClose: () => alert("Action cancelled"),
    },
};
