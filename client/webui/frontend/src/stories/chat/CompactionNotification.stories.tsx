import { CompactionNotification } from "@/lib/components/chat/CompactionNotification";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";

const meta = {
    title: "Chat/CompactionNotification",
    component: CompactionNotification,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Notification displayed when conversation history has been automatically summarized due to context limits. Shows a collapsible card with the summary text.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <div style={{ padding: "2rem", maxWidth: "800px", height: "100vh" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof CompactionNotification>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Interactive: Story = {
    args: {
        data: {
            type: "compaction_notification",
            summary:
                "After previously receiving a pizza recipe and topping ideas from the AI, the user has shifted the topic to cooking equipment. They asked whether they should get a pizza stone. In response, the AI provided a detailed guide (`pizza_stone_guide.md`) that outlines the pros (e.g., crispier crust), cons (e.g., preheating, fragility), and several alternatives like a baking steel or a cast-iron skillet to help the user make an informed decision.",
            is_background: false,
        },
    },
};

export const Background: Story = {
    args: {
        data: {
            type: "compaction_notification",
            summary:
                "The agent processed a scheduled data pipeline job that involved extracting customer records, transforming the data format, and loading results into the analytics database. The pipeline completed successfully with 15,000 records processed.",
            is_background: true,
        },
    },
};

export const ShortSummary: Story = {
    args: {
        data: {
            type: "compaction_notification",
            summary: "User asked about weather forecasts and received a 5-day outlook for Toronto.",
            is_background: false,
        },
    },
};

export const LongSummary: Story = {
    args: {
        data: {
            type: "compaction_notification",
            summary:
                "The conversation covered multiple topics over an extended session. Initially, the user asked about setting up a Python development environment, and the AI walked through installing Python 3.12, setting up a virtual environment with uv, and configuring VS Code. The user then pivoted to database design, asking about schema design for a multi-tenant SaaS application. The AI provided a detailed schema with tenant isolation using row-level security in PostgreSQL. Following that, the user asked about deployment strategies, and the AI outlined a blue-green deployment approach using AWS ECS with Fargate. The conversation also touched on CI/CD pipeline configuration with GitHub Actions, including test automation, Docker image building, and automated deployments to staging and production environments. Finally, the user asked about monitoring and observability, receiving recommendations for structured logging with OpenTelemetry, metrics collection with Prometheus, and distributed tracing.",
            is_background: false,
        },
    },
};
