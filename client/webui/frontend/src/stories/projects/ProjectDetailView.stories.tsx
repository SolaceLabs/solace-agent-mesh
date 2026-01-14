import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { ProjectDetailView } from "@/lib";
import { populatedProject, emptyProject } from "./data";
import type { Session } from "@/lib/types/fe";
import type { ArtifactInfo } from "@/lib/types";
import { getMockAgentCards, mockAgentCards } from "../mocks/data";
import { transformAgentCard } from "@/lib/hooks/useAgentCards";

// ============================================================================
// Mock Data
// ============================================================================

const mockSessions: Session[] = [
    {
        id: "session-1",
        name: "Debug authentication flow",
        createdTime: new Date("2024-03-18T10:30:00Z").toISOString(),
        updatedTime: new Date("2024-03-20T14:22:00Z").toISOString(),
        projectId: populatedProject.id,
        projectName: populatedProject.name,
    },
    {
        id: "session-2",
        name: "Implement password reset",
        createdTime: new Date("2024-03-15T09:15:00Z").toISOString(),
        updatedTime: new Date("2024-03-19T16:45:00Z").toISOString(),
        projectId: populatedProject.id,
        projectName: populatedProject.name,
    },
];

const mockArtifacts: ArtifactInfo[] = [
    {
        filename: "api-documentation.pdf",
        mime_type: "application/pdf",
        size: 524288,
        last_modified: new Date("2024-03-15T10:00:00Z").toISOString(),
        description: "API reference documentation",
    },
    {
        filename: "architecture-diagram.png",
        mime_type: "image/png",
        size: 204800,
        last_modified: new Date("2024-03-18T14:30:00Z").toISOString(),
        description: "System architecture overview",
    },
    {
        filename: "package.json",
        mime_type: "application/json",
        size: 1024,
        last_modified: new Date("2024-03-17T09:45:00Z").toISOString(),
        description: "Project dependencies and scripts",
    },
    {
        filename: "README.md",
        mime_type: "text/markdown",
        size: 4096,
        last_modified: new Date("2024-03-16T12:20:00Z").toISOString(),
        description: "Project overview and setup instructions",
    },
];

const transformedMockAgents = mockAgentCards.concat(getMockAgentCards(2)).map(transformAgentCard);
const agentNameDisplayNameMap = transformedMockAgents.reduce(
    (acc, agent) => {
        if (agent.name) acc[agent.name] = agent.displayName || agent.name;
        return acc;
    },
    {} as Record<string, string>
);

// ============================================================================
// MSW Handlers
// ============================================================================

const handlers = [
    http.get("/api/v1/sessions", ({ request }) => {
        const url = new URL(request.url);
        const projectId = url.searchParams.get("project_id");

        if (projectId === populatedProject.id) {
            return HttpResponse.json({ data: mockSessions });
        }
        return HttpResponse.json({ data: [] });
    }),

    http.get("/api/v1/projects/:projectId/artifacts", ({ params }) => {
        const { projectId } = params;

        if (projectId === populatedProject.id) {
            return HttpResponse.json(mockArtifacts);
        }
        return HttpResponse.json([]);
    }),
];

// ============================================================================
// Story Configuration
// ============================================================================

const meta = {
    title: "Pages/Projects/ProjectDetailView",
    component: ProjectDetailView,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Detailed view of a single project showing chats, instructions, default agent, and knowledge sections.",
            },
        },
        msw: { handlers },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof ProjectDetailView>;

export default meta;
type Story = StoryObj<typeof meta>;

// ============================================================================
// Stories
// ============================================================================

/**
 * Default state with all sections populated with mock data
 */
export const Default: Story = {
    args: {
        project: populatedProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    parameters: {},
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByTestId("editDetailsButton")).toBeVisible();
        expect(await canvas.findByTestId("startNewChatButton")).toBeVisible();
    },
};

/**
 * Empty state when a new project is created with no content
 */
export const Empty: Story = {
    args: {
        project: emptyProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    parameters: {
        chatContext: {
            agents: transformedMockAgents,
            agentNameDisplayNameMap,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        /**
         * ensure start new chat button is visible by id
        */
        const startNewChatNoChatsButton = await canvas.findByTestId("startNewChatButtonNoChats");
        expect(startNewChatNoChatsButton).toBeVisible();
    },
};
