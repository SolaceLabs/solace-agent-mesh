import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, within } from "storybook/test";
import { ProjectsPage } from "@/lib";
import { allProjects } from "../data/projects";

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

/**
 * Default state with multiple projects
 */
export const Default: Story = {
    parameters: {
        projectContext: {
            projects: allProjects,
            filteredProjects: allProjects,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByTestId("refreshProjects")).toBeVisible();
        expect(await canvas.findByTestId("createProjectCard")).toBeVisible();
        for (const project of allProjects) {
            expect(await canvas.findByText(project.name)).toBeVisible();
        }
    },
};

/**
 * State with a search term filtering projects
 */
export const WithSearchTerm: Story = {
    parameters: {
        projectContext: {
            projects: allProjects,
            filteredProjects: [allProjects.find(p => p.name === "Weather App")!],
            searchQuery: "Weather",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const searchInput = await canvas.findByTestId("projectSearchInput");
        searchInput.focus();

        expect(await canvas.findByTestId("createProjectCard")).toBeVisible();
    },
};

/**
 * State with no projects matching the search/filter
 */
export const WithNoResults: Story = {
    parameters: {
        projectContext: {
            projects: allProjects,
            filteredProjects: [],
            searchQuery: "Nonexistent Project",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("No Projects Match Your Filter")).toBeVisible();
        expect(await canvas.findByTestId("Clear Filter")).toBeVisible();
    },
};

/**
 * State with no projects
 */
export const NoProjects: Story = {
    parameters: {
        projectContext: {},
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByTestId("Create New Project")).toBeVisible();
    },
};

/**
 * Loading state while projects are being fetched
 */
export const Loading: Story = {
    parameters: {
        projectContext: {
            isLoading: true,
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(await canvas.findByText("Loading projects...")).toBeVisible();
    },
};
