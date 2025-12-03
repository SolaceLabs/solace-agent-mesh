import { Toast } from "@/lib/components/toast";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, screen, within } from "storybook/test";

const meta = {
    title: "Common/Toast",
    component: Toast,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The Toast component for displaying brief messages to users",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return (
                <div
                    style={{
                        display: "flex",
                        alignItems: "flex-end",
                        justifyContent: "center",
                        height: "100vh",
                        width: "100vw",
                        paddingBottom: "2rem",
                    }}
                >
                    {storyResult}
                </div>
            );
        },
    ],
} satisfies Meta<typeof Toast>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        id: "default-toast",
        message: "Toast message goes here",
    },
    play: async () => {
        const toast = await screen.findByRole("alert");
        expect(within(toast).getByText("Toast message goes here")).toBeInTheDocument();
    },
};

export const Success: Story = {
    args: {
        id: "success-toast",
        message: "Success toast message goes here",
        type: "success",
    },
    play: async () => {
        const toast = await screen.findByRole("alert");
        expect(within(toast).getByText("Success toast message goes here")).toBeInTheDocument();
    },
};

export const Warning: Story = {
    args: {
        id: "warning-toast",
        message: "Warning toast message goes here",
        type: "warning",
    },
    play: async () => {
        const toast = await screen.findByRole("alert");
        expect(within(toast).getByText("Warning toast message goes here")).toBeInTheDocument();
    },
};
