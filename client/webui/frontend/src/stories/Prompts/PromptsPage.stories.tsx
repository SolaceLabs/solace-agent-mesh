import { PromptsPage } from "@/lib";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Pages/Prompts/PromptsPage",
    component: PromptsPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The main chat page component that displays the chat interface, side panels, and handles user interactions.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        chatContext: {
            useLoaderData: () => ({}),
        },
    },
};
