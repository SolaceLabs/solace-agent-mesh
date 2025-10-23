import { MessageBanner } from "@/lib/components/common/MessageBanner";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Common/MessageBanner",
    component: MessageBanner,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The Message banner component that displays messages in a banner that can be dismissable",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ padding: "2rem", height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof MessageBanner>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        message: "Banner message goes here",
    },
};

export const ErrorBanner: Story = {
    args: {
        variant: "error",
        message: "Something went wrong",
    },
};

export const WarningBanner: Story = {
    args: {
        variant: "warning",
        message: "Ensure directory is empty before running this command",
    },
};

export const InfoBanner: Story = {
    args: {
        variant: "info",
        message: "Ensure all dependencies are installed",
    },
};

export const SuccessBanner: Story = {
    args: {
        variant: "success",
        message: "Updated details successfully",
    },
};

export const DismissableBanner: Story = {
    args: {
        variant: "info",
        dismissible: true,
        message: "Dissms me",
        onDismiss: () => alert("Banner will be dismissed"),
    },
};
