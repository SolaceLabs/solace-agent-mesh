import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { userEvent, within, expect } from "storybook/test";
import { PromptsPage } from "@/lib/components/pages/PromptsPage";

const meta = {
    title: "Pages/PromptsPage",
    component: PromptsPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "The prompts library page for managing reusable prompt templates.",
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

/**
 * Default view showing the prompts library with multiple prompts
 */
export const Default: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        await canvas.findByText("Bug Report");
        await canvas.findByText("Documentation Writer");
        
        // Verify search input exists
        await canvas.findByTestId("promptSearchInput");
    },
};

/**
 * Empty state when no prompts exist
 */
export const EmptyState: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Verify empty state is shown
        await canvas.findByText("No prompts yet");
        await canvas.findByText("Create your first prompt template");
        
        // Verify create buttons exist
        await canvas.findByRole("button", { name: /Create Manually/i });
        await canvas.findByRole("button", { name: /AI-Assisted/i });
    },
};

/**
 * Search functionality - finding prompts
 */
export const SearchPrompts: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        
        // Search for "review"
        const searchInput = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(searchInput, "review");
        
        // Should show Code Review Template
        await canvas.findByText("Code Review Template");
        
        // Should not show other prompts
        expect(canvas.queryByText("Bug Report")).not.toBeInTheDocument();
        expect(canvas.queryByText("Documentation Writer")).not.toBeInTheDocument();
    },
};

/**
 * Search with no results
 */
export const SearchNoResults: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        
        // Search for non-existent prompt
        const searchInput = await canvas.findByTestId("promptSearchInput");
        await userEvent.type(searchInput, "nonexistent");
        
        // Should show no results message
        await canvas.findByText("No prompts match your search");
    },
};

/**
 * Filter by category
 */
export const FilterByCategory: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        
        // Open category filter
        const filterButton = await canvas.findByRole("button", { name: /Tags/i });
        await userEvent.click(filterButton);
        
        // Select Development category
        const developmentCheckbox = await canvas.findByLabelText("Development");
        await userEvent.click(developmentCheckbox);
        
        // Should show only Development prompts
        await canvas.findByText("Code Review Template");
        expect(canvas.queryByText("Bug Report")).not.toBeInTheDocument();
    },
};

/**
 * Pinned prompts appear first
 */
export const PinnedPromptsFirst: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        
        // Get all prompt cards
        const promptCards = canvas.getAllByTestId("prompt-card");
        
        // First card should be the pinned one (Code Review Template)
        const firstCard = promptCards[0];
        expect(within(firstCard).getByText("Code Review Template")).toBeInTheDocument();
    },
};

/**
 * Click on a prompt to view details
 */
export const ViewPromptDetails: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        const promptCard = await canvas.findByText("Code Review Template");
        
        // Click on the prompt
        await userEvent.click(promptCard);
        
        // Side panel should open with details
        // Note: This would require the side panel to be visible in the story
        // For now, we just verify the click works
    },
};

/**
 * Refresh prompts list
 */
export const RefreshPrompts: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Wait for prompts to load
        await canvas.findByText("Code Review Template");
        
        // Click refresh button
        const refreshButton = await canvas.findByTestId("refreshPrompts");
        await userEvent.click(refreshButton);
        
        // Prompts should still be visible after refresh
        await canvas.findByText("Code Review Template");
    },
};

/**
 * Responsive design - tablet viewport
 */
export const TabletView: Story = {
    parameters: {
        viewport: {
            defaultViewport: "tablet",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Verify prompts are visible on tablet
        await canvas.findByText("Code Review Template");
        await canvas.findByTestId("promptSearchInput");
    },
};

/**
 * Responsive design - mobile viewport
 */
export const MobileView: Story = {
    parameters: {
        viewport: {
            defaultViewport: "mobile1",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        
        // Verify prompts are visible on mobile
        await canvas.findByText("Code Review Template");
        await canvas.findByTestId("promptSearchInput");
    },
};

/**
 * Loading state
 */
export const Loading: Story = {
    play: async ({ canvasElement }) => {
        // canvasElement is available but not used in this story
        void canvasElement;
        
        // Note: Loading state is brief when running against real backend
        // This story demonstrates the loading UI that appears during data fetch
    },
};