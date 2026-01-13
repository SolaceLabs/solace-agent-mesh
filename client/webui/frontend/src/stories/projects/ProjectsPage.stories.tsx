import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { within } from "storybook/test";
import { ProjectsPage } from "@/lib";
import { defaultProjects } from "./data";

const meta = {
    title: "Pages/Projects/ProjectsPage",
    component: ProjectsPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The main projects page component that displays project cards, search functionality, and handles project management interactions.",
            },
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);

            return <div style={{ height: "100vh", width: "100vw" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof ProjectsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        projectContext: {
            projects: defaultProjects,
            filteredProjects: defaultProjects,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByTestId("refreshProjects");
        await canvas.findByTestId("createProjectCard");
        await canvas.findByText("Weather App");
        await canvas.findByText("E-commerce Platform");
    },
};

export const WithSearchTerm: Story = {
    parameters: {
        projectContext: {
            projects: defaultProjects,
            filteredProjects: [defaultProjects[0]],
            searchQuery: "Weather",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const searchInput = await canvas.findByTestId("projectSearchInput");
        searchInput.focus();

        await canvas.findByTestId("createProjectCard");
    },
};

export const NoProjects: Story = {
    parameters: {
        projectContext: {},
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("No Projects Found");
        await canvas.findByText("Create New Project");
    },
};

export const Loading: Story = {
    parameters: {
        projectContext: {
            isLoading: true,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByText("Loading projects...");
    },
};
