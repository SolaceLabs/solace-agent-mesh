import { EmptyState } from "@/lib/components/common/EmptyState";
import type { Meta, StoryObj, StoryFn, StoryContext } from "@storybook/react-vite";

const meta = {
    title: "Common/EmptyState",
    component: EmptyState,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The Empty state component that displays error messages or not-found messages.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ padding: "2rem", height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof EmptyState>;

export default meta;

type Story = StoryObj<typeof meta>;

export const ErrorMessage: Story = {
    args: {
        title: "Unable to retrieve data",
        subtitle: "Something went wrong.",
        buttons: [{ text: "Go Back", variant: "default", onClick: () => alert("Button will go back") }],
    },
};

export const NotFoundMessage: Story = {
    args: {
        title: "No results",
        variant: "notFound",
        subtitle: "We couldn't find what you were looking for",
        buttons: [{ text: "Go Back", variant: "default", onClick: () => alert("Button will go back") }],
    },
};

export const LoadingMessage: Story = {
    args: {
        title: "Loading Data...",
        variant: "loading",
        subtitle: "Hang tight",
    },
};

export const NoImageMessage: Story = {
    args: {
        title: "No Image",
        subtitle: "This message has no image",
        variant: "noImage",
        buttons: [{ text: "Go Back", variant: "default", onClick: () => alert("Button will go back") }],
    },
};

export const NoSubtitleMessage: Story = {
    args: {
        title: "No Subtitle",
        variant: "error",
        buttons: [{ text: "Go Back", variant: "default", onClick: () => alert("Button will go back") }],
    },
};

export const NoButtonsMessage: Story = {
    args: {
        title: "No Buttons",
        subtitle: "I have no buttons",
        variant: "error",
    },
};

export const MultiActionMessage: Story = {
    args: {
        title: "Something went wrong",
        subtitle: "There's multiple options to choose from",
        buttons: [
            { text: "Go Back", variant: "link", onClick: () => alert("Button will go back") },
            { text: "Go Home", variant: "outline", onClick: () => alert("Button will go home") },
            { text: "Try Again", variant: "default", onClick: () => alert("Button will try again") },
        ],
    },
};

export const TitleOnlyMessage: Story = {
    args: { title: "Something went wrong" },
};
