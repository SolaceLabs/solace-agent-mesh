import { ResearchPlanVerification } from "@/lib/components/research/ResearchPlanVerification";
import { StoryProvider } from "../mocks/StoryProvider";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Chat/ResearchPlanVerification",
    component: ResearchPlanVerification,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Interactive prompt shown before a deep research task runs. The user can accept the plan, edit steps, or cancel. Hidden once the underlying data part is marked as responded.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return (
                <StoryProvider>
                    <div style={{ padding: "2rem", maxWidth: "800px" }}>{storyResult}</div>
                </StoryProvider>
            );
        },
    ],
} satisfies Meta<typeof ResearchPlanVerification>;

export default meta;

type Story = StoryObj<typeof meta>;

const basePlan = {
    type: "deep_research_plan" as const,
    plan_id: "plan-demo-123",
    agent_name: "ResearchAgent",
    title: "Impact of LLM-assisted coding on developer productivity",
    research_question: "How has LLM-assisted coding changed developer productivity over the past year?",
    steps: [
        "Survey recent industry studies on LLM-assisted coding adoption.",
        "Compare productivity metrics before and after widespread tool rollout.",
        "Identify tasks where AI assistance shows the largest gains.",
        "Synthesize findings into a concise report.",
    ],
    research_type: "in-depth",
    max_iterations: 4,
    max_runtime_seconds: 300,
    sources: ["web"],
};

export const Pending: Story = {
    args: { planData: basePlan },
};

export const SingleStep: Story = {
    args: {
        planData: {
            ...basePlan,
            steps: ["Find the current population of Toronto."],
        },
    },
};

export const AlreadyResponded: Story = {
    args: {
        planData: { ...basePlan, responded: "start" },
    },
    parameters: {
        docs: {
            description: {
                story: "When `responded` is set (e.g. after a session reload), the component renders nothing.",
            },
        },
    },
};
