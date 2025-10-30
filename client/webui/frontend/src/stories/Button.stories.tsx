import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { Button } from "@/lib";

const meta = {
    title: "Common/Button",
    component: Button,
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
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    args: {
        variant: "default",
        children: "Default Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Secondary: Story = {
    args: {
        variant: "secondary",
        children: "Secondary Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Outline: Story = {
    args: {
        variant: "outline",
        children: "Outline Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Link: Story = {
    args: {
        variant: "link",
        children: "Link Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Ghost: Story = {
    args: {
        variant: "ghost",
        children: "Ghost Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Destructive: Story = {
    args: {
        variant: "destructive",
        children: "Destructive Button",
        disabled: false,
        onClick: () => alert("Button does something"),
    },
};

export const Disabled: Story = {
    args: {
        variant: "default",
        disabled: true,
        children: "Disabled Button",
    },
};
