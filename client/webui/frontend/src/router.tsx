import { createHashRouter, Navigate } from "react-router-dom";

import { AgentMeshPage, ArtifactsPage, ChatPage, ProjectsPage, PromptsPage, RecentChatsPage, ScheduledTasksPage, SharedChatViewPage } from "./lib";
import { WorkflowVisualizationPage } from "./lib/components/workflowVisualization";
import { ModelDetailsPage, ModelEditPage } from "./lib/components/models";
import { SharedSessionPage } from "./lib/components/pages/SharedSessionPage";
import AppLayout from "./AppLayout";

export const createRouter = () => {
    return createHashRouter([
        // Public share route (outside AppLayout)
        {
            path: "/share/:shareId",
            element: <SharedSessionPage />,
        },
        {
            path: "/",
            element: <AppLayout />,
            children: [
                {
                    index: true,
                    element: <Navigate to="/chat" replace />,
                },
                {
                    path: "chat",
                    element: <ChatPage />,
                },
                {
                    // Embedded, chat-only single-agent surface (?agent=Foo). Reuses ChatPage;
                    // ChatSurfaceProvider keys the embedded layout off the /embed/* route path.
                    path: "embed/chat",
                    element: <ChatPage />,
                },
                {
                    // Embedded "View All" — agent-scoped recent chats. Reuses RecentChatsPage,
                    // which trims its chrome and scopes to ?agent= when the surface is embedded.
                    path: "embed/recent-chats",
                    element: <RecentChatsPage />,
                },
                {
                    path: "recent-chats",
                    element: <RecentChatsPage />,
                },
                {
                    path: "shared-chat/:shareId",
                    element: <SharedChatViewPage />,
                },
                {
                    path: "projects",
                    children: [
                        {
                            index: true,
                            element: <ProjectsPage />,
                        },
                        {
                            path: ":id",
                            element: <ProjectsPage />,
                            loader: ({ params }) => {
                                return { projectId: params.id };
                            },
                        },
                    ],
                },
                {
                    path: "artifacts",
                    element: <ArtifactsPage />,
                },
                {
                    path: "prompts",
                    children: [
                        {
                            index: true,
                            element: <PromptsPage />,
                        },
                        {
                            path: "new",
                            element: <PromptsPage />,
                            loader: ({ request }) => {
                                const url = new URL(request.url);
                                const mode = url.searchParams.get("mode") || "manual";
                                return { view: "builder", mode };
                            },
                        },
                        {
                            path: ":id/edit",
                            element: <PromptsPage />,
                            loader: ({ params }) => {
                                return { promptId: params.id, view: "builder", mode: "edit" };
                            },
                        },
                        {
                            path: ":id/versions",
                            element: <PromptsPage />,
                            loader: ({ params }) => {
                                return { promptId: params.id, view: "versions" };
                            },
                        },
                    ],
                },
                {
                    path: "agents",
                    children: [
                        {
                            index: true,
                            element: <AgentMeshPage />,
                        },
                        {
                            path: "workflows/:workflowName",
                            element: <WorkflowVisualizationPage />,
                        },
                    ],
                },
                {
                    path: "models",
                    children: [
                        {
                            path: "new/edit",
                            element: <ModelEditPage />,
                        },
                        {
                            path: ":id/edit",
                            element: <ModelEditPage />,
                        },
                        {
                            path: ":id",
                            element: <ModelDetailsPage />,
                        },
                    ],
                },
                {
                    path: "scheduled-tasks",
                    element: <ScheduledTasksPage />,
                },
                {
                    path: "*",
                    element: <Navigate to="/chat" replace />,
                },
            ],
        },
    ]);
};
