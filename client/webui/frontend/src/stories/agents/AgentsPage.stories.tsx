import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { userEvent, within } from "storybook/test";
import { AgentMeshPage } from "@/lib";

const meta = {
    title: "Pages/Agents/AgentsPage",
    component: AgentMeshPage,
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
} satisfies Meta<typeof AgentMeshPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByTestId("refreshAgents");
        await canvas.findByTestId("clickForDetails");
    },
};

export const FilterNoResultsFound: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const input = await canvas.findByTestId("agentSearchInput");
        await userEvent.type(input, "test");

        await canvas.findByText("No Agents Match Your Filter");
    },
};
