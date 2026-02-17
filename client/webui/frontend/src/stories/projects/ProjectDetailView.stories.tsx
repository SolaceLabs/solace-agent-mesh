import React, { useEffect } from "react";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, screen, userEvent, waitFor, within } from "storybook/test";
import { http, HttpResponse } from "msw";

import { ProjectDetailView } from "@/lib";
import { transformAgentCard, useSSEContext } from "@/lib/hooks";

import { getMockAgentCards, mockAgentCards } from "../mocks/data";
import { emptyProject, imageArtifact, jsonArtifact, markdownArtifact, ownerWithAuthorization, pdfArtifact, populatedProject, sessions } from "../data";

// ============================================================================
// Mocks
// ============================================================================

const mockArtifacts = [pdfArtifact, imageArtifact, jsonArtifact, markdownArtifact];
const transformedMockAgents = mockAgentCards.concat(getMockAgentCards(2)).map(transformAgentCard);
const agentNameDisplayNameMap = transformedMockAgents.reduce(
    (acc, agent) => {
        if (agent.name) acc[agent.name] = agent.displayName || agent.name;
        return acc;
    },
    {} as Record<string, string>
);

/**
 * Helper to register a mock indexing task on mount
 */
const MockIndexingTask: React.FC<{ projectId: string; children: React.ReactNode }> = ({ projectId, children }) => {
    const { registerTask } = useSSEContext();

    useEffect(() => {
        registerTask({
            taskId: "mock-indexing-task",
            sseUrl: "/api/v1/sse/subscribe/mock-indexing-task",
            metadata: { projectId },
        });
    }, [registerTask, projectId]);

    return <>{children}</>;
};

/**
 * Helper to register a mock failed indexing task on mount
 */
const MockFailedIndexingTask: React.FC<{ projectId: string; children: React.ReactNode }> = ({ projectId, children }) => {
    const { registerTask } = useSSEContext();

    useEffect(() => {
        registerTask({
            taskId: "mock-failed-indexing-task",
            sseUrl: "/api/v1/sse/subscribe/mock-failed-indexing-task",
            metadata: { projectId },
        });
    }, [registerTask, projectId]);

    return <>{children}</>;
};

// ============================================================================
// MSW Handlers
// ============================================================================

const handlers = [
    http.get("/api/v1/sessions", ({ request }) => {
        const url = new URL(request.url);
        const projectId = url.searchParams.get("project_id");

        if (projectId === populatedProject.id) {
            return HttpResponse.json({ data: sessions });
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

    // Mock SSE endpoint for indexing - keeps connection open indefinitely
    http.get("/api/v1/sse/subscribe/mock-indexing-task", () => {
        const stream = new ReadableStream({
            start(controller) {
                // Send initial connection event
                controller.enqueue(new TextEncoder().encode('event: index_message\ndata: {"type":"task_started"}\n\n'));
            },
        });

        return new HttpResponse(stream, {
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                Connection: "keep-alive",
            },
        });
    }),

    // Mock SSE endpoint for failed indexing - sends error then closes
    http.get("/api/v1/sse/subscribe/mock-failed-indexing-task", () => {
        const stream = new ReadableStream({
            async start(controller) {
                // Small delay to allow EventSource to fully connect and register handlers
                await new Promise(resolve => setTimeout(resolve, 100));
                // Send error event
                controller.enqueue(new TextEncoder().encode('event: index_message\ndata: {"type":"conversion_failed","error":"Failed to convert \'document.pdf\'"}\n\n'));
                controller.close();
            },
        });

        return new HttpResponse(stream, {
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                Connection: "keep-alive",
            },
        });
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
            // Clear any stale SSE tasks from sessionStorage on story mount
            sessionStorage.removeItem("sam_sse_tasks");
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
    parameters: ownerWithAuthorization("user-id"),
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
        const startNewChatNoChatsButton = await canvas.findByTestId("startNewChatButtonNoChats");
        expect(startNewChatNoChatsButton).toBeVisible();
    },
};

/**
 * Edit Details Dialog - Tests the embedded edit dialog for project name and description
 */
export const EditDetailsDialog: Story = {
    args: {
        project: populatedProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        const editButton = await canvas.findByTestId("editDetailsButton");
        expect(editButton).toBeVisible();
        await userEvent.click(editButton);

        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        const dialogContent = within(dialog);

        expect(await dialogContent.findByText("Edit Project Details")).toBeInTheDocument();
        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeEnabled();
        expect(await dialogContent.findByRole("button", { name: "Discard Changes" })).toBeEnabled();
    },
};

/**
 * Edit Details Dialog - Description character limit (1000 characters)
 */
export const EditDetailsDescriptionLimit: Story = {
    args: {
        project: populatedProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        const editButton = await canvas.findByTestId("editDetailsButton");
        await userEvent.click(editButton);

        const dialog = await screen.findByRole("dialog");
        const dialogContent = within(dialog);
        const descriptionInput = await dialogContent.findByPlaceholderText("Project description");

        await userEvent.clear(descriptionInput);
        const atLimitText = "a".repeat(1000);
        await userEvent.click(descriptionInput);
        await userEvent.paste(atLimitText);
        expect(await dialogContent.findByText("1000 / 1000")).toBeInTheDocument();

        await userEvent.type(descriptionInput, "b");
        expect(await dialogContent.findByText("Description must be less than 1000 characters")).toBeInTheDocument();

        expect(await dialogContent.findByRole("button", { name: "Save" })).toBeDisabled();
    },
};

/**
 * Indexing state - Shows the UI when project files are being indexed.
 * All action buttons should be disabled and an info banner should be visible.
 */
export const Indexing: Story = {
    args: {
        project: populatedProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    parameters: ownerWithAuthorization("user-id"),
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <MockIndexingTask projectId={populatedProject.id}>{storyResult}</MockIndexingTask>;
        },
    ],
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify info banner is shown
        expect(await canvas.findByTestId("messageBanner")).toBeVisible();

        // Verify buttons disabled
        expect(await canvas.findByTestId("editDetailsButton")).toBeDisabled();
        expect(await canvas.findByTestId("editInstructions")).toBeDisabled();
        expect(await canvas.findByTestId("editDefaultAgent")).toBeDisabled();
        expect(await canvas.findByTestId("startNewChatButton")).toBeDisabled();
    },
};

/**
 * Indexing Error state - Shows the UI when indexing fails with an error.
 * The error message should be displayed and buttons should be re-enabled.
 */
export const IndexingError: Story = {
    args: {
        project: populatedProject,
        onBack: () => alert("Will navigate back to project list"),
        onStartNewChat: () => alert("Will start a new chat"),
        onChatClick: (sessionId: string) => alert("Will open chat " + sessionId),
    },
    parameters: ownerWithAuthorization("user-id"),
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <MockFailedIndexingTask projectId={populatedProject.id}>{storyResult}</MockFailedIndexingTask>;
        },
    ],
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify info banner is shown
        expect(await canvas.findByTestId("messageBanner")).toBeVisible();

        // Verify buttons enabled - wait for first to ensure page is updated
        await waitFor(async () => expect(await canvas.findByTestId("editDetailsButton", {}, { timeout: 2000 })).toBeEnabled());
        expect(await canvas.findByTestId("editInstructions")).toBeEnabled();
        expect(await canvas.findByTestId("editDefaultAgent")).toBeEnabled();
        expect(await canvas.findByTestId("startNewChatButton")).toBeEnabled();
    },
};
