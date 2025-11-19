import { Button } from "@/lib";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { Sparkles } from "lucide-react";

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

export const CustomIconBanner: Story = {
    args: {
        variant: "info",
        message: "This banner has a custom icon",
        icon: <Sparkles className="size-4" />,
    },
};

export const DismissibleBanner: Story = {
    args: {
        variant: "info",
        dismissible: true,
        message: "Dissms me",
        onDismiss: () => alert("Banner will be dismissed"),
    },
};

export const BannerWithCustomButton: Story = {
    args: {
        variant: "warning",
        message: "Dissms me",
        button: (
            <Button variant="outline" className="border-white px-1 py-1 text-xs hover:!bg-current/50" onClick={() => alert("Custom button will do something")}>
                Custom button
            </Button>
        ),
    },
};

export const BannerWithCustomButtonAndSameStyles: Story = {
    args: {
        variant: "warning",
        message: "Dissms me",
        button: (
            <Button variant="outline" className="border-white px-1 py-1 text-xs hover:!bg-current/50" onClick={() => alert("Custom button will do something")}>
                Custom button
            </Button>
        ),
    },
};

export const LongMessage: Story = {
    args: {
        variant: "info",
        dismissible: true,
        message:
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
        button: (
            <Button variant="outline" className="border-white px-1 py-1 text-xs hover:!bg-current/50" onClick={() => alert("Custom button will do something")}>
                Click Here
            </Button>
        ),
        onDismiss: () => alert("Banner will be dismissed"),
    },
};
