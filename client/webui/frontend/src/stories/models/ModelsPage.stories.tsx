import type { Meta, StoryObj } from "@storybook/react-vite";
import { within, expect, userEvent } from "storybook/test";
import { http, HttpResponse, delay } from "msw";

import { AgentMeshPage } from "@/lib/components/pages";
import { mockModelConfigs, mockModelConfigsWithUnconfiguredDefaults } from "../data/models";
import { createOpenFeatureDecorator } from "../mocks/OpenFeatureDecorator";
import { InvalidateModelCacheDecorator } from "../decorators/InvalidateModelCacheDecorator";

const OpenFeatureDecorator = createOpenFeatureDecorator({ flags: { model_config_ui: true } });

const successHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: mockModelConfigs, total: mockModelConfigs.length });
    }),
];

const loadingHandlers = [
    http.get("*/api/v1/platform/models", async () => {
        await delay("infinite");
        return HttpResponse.json({ data: [], total: 0 });
    }),
];

const emptyHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: [], total: 0 });
    }),
];

const errorHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.error();
    }),
];

const meta = {
    title: "Pages/Models/ModelsPage",
    component: AgentMeshPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Model configurations list view with pagination and filtering.",
            },
        },
    },
    decorators: [
        OpenFeatureDecorator,
        InvalidateModelCacheDecorator,
        Story => (
            <div style={{ height: "100vh", width: "100vw" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof AgentMeshPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
    parameters: {
        msw: { handlers: successHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify table renders with data (system-created aliases are title-cased via getDisplayAliasName)
        await canvas.findByText("Planning");
        await canvas.findByText("General");
        await canvas.findByText("Image Gen");

        // Verify columns exist
        expect(canvas.getByText("Name")).toBeInTheDocument();
        expect(canvas.getByText("Model")).toBeInTheDocument();
        expect(canvas.getByText("Model Provider")).toBeInTheDocument();

        // Verify pagination controls don't show (only 8 models fit on one page)
        expect(canvas.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();

        // Verify default badges are rendered for General and Planning models
        const defaultBadges = await canvas.findAllByText("Default");
        expect(defaultBadges.length).toBe(2);

        // Verify the badges are in the correct rows (General and Planning)
        const generalRow = canvas.getByRole("row", { name: /General/i });
        const planningRow = canvas.getByRole("row", { name: /Planning/i });

        const generalBadge = within(generalRow).getByText("Default");
        const planningBadge = within(planningRow).getByText("Default");

        expect(generalBadge).toBeInTheDocument();
        expect(planningBadge).toBeInTheDocument();

        // Verify "Add Model" button appears on the Models tab and navigates when clicked
        const addModelButton = canvas.getByRole("button", { name: /Add Model/i });
        expect(addModelButton).toBeInTheDocument();
        await userEvent.click(addModelButton);

        // After clicking, navigation to /models/new/edit unmounts the models table
        expect(canvas.queryByText("Planning")).not.toBeInTheDocument();
    },
};

export const Loading: Story = {
    parameters: {
        msw: { handlers: loadingHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify loading state is shown
        await canvas.findByText("Loading Models...");
        expect(canvas.getByText("Loading Models...")).toBeInTheDocument();
    },
};

export const Empty: Story = {
    parameters: {
        msw: { handlers: emptyHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify empty state is shown
        await canvas.findByText("Match AI Models to Your Team's Workflows");
        expect(canvas.getByText("Match AI Models to Your Team's Workflows")).toBeInTheDocument();
    },
};

export const Error: Story = {
    parameters: {
        msw: { handlers: errorHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify error state is shown
        await canvas.findByText(/Error loading models/);
        expect(canvas.getByText(/Error loading models/)).toBeInTheDocument();
    },
};

export const Sorting: Story = {
    parameters: {
        msw: { handlers: successHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Wait for table to render
        await canvas.findByText("Aws");

        // Default sort: Name A→Z (sorted by alias field).
        // Mock data aliases: aws, azure, custom_model, general, gemini, image_gen, local, planning, vertex
        const rows = canvas.getAllByRole("row");
        // rows[0] = header row; rows[1] = first data row
        expect(within(rows[1]).getByText("Aws")).toBeInTheDocument();
        expect(within(rows.at(-1)!).getByText("Vertex")).toBeInTheDocument();

        // Verify all three column headers have sort buttons
        expect(canvas.getByRole("button", { name: "Name" })).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: "Model" })).toBeInTheDocument();
        expect(canvas.getByRole("button", { name: "Model Provider" })).toBeInTheDocument();

        // Click Name header to toggle to Z→A
        await userEvent.click(canvas.getByRole("button", { name: "Name" }));

        // After toggle: first data row should be "Vertex"
        await canvas.findByText("Vertex");
        const rowsDesc = canvas.getAllByRole("row");
        expect(within(rowsDesc[1]).getByText("Vertex")).toBeInTheDocument();
        expect(within(rowsDesc.at(-1)!).getByText("Aws")).toBeInTheDocument();

        // Click Name header again to restore A→Z
        await userEvent.click(canvas.getByRole("button", { name: "Name" }));
        await canvas.findByText("Aws");
        const rowsAsc = canvas.getAllByRole("row");
        expect(within(rowsAsc[1]).getByText("Aws")).toBeInTheDocument();
    },
};

export const WithPagination: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/platform/models", () => {
                    const data = Array.from({ length: 45 }, (_, i) => ({
                        id: `model-${i}`,
                        alias: `model-${i}`,
                        provider: i % 3 === 0 ? "anthropic" : i % 3 === 1 ? "openai" : "vertex_ai",
                        modelName: `test-model-${i}`,
                        apiBase: "https://api.example.com",
                        authType: "apikey",
                        authConfig: { type: "apikey" },
                        modelParams: {},
                        description: `Test model ${i}`,
                        createdBy: "system",
                        updatedBy: "system",
                        createdTime: Date.now(),
                        updatedTime: Date.now(),
                    }));
                    return HttpResponse.json({
                        data,
                        total: data.length,
                    });
                }),
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify pagination renders with first page of 45 models
        // system-created aliases are title-cased, but hyphens are preserved (only underscores split)
        await canvas.findByText("Model-0");
        await canvas.findByText("Model-19");
        expect(canvas.getByText("Model-0")).toBeInTheDocument();

        // Verify pagination controls ARE visible (45 models exceed one page)
        const paginationNav = canvas.getByRole("navigation", { name: /pagination/i });
        expect(paginationNav).toBeInTheDocument();
    },
};

export const UnconfiguredDefaults: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/platform/models", () => {
                    return HttpResponse.json({ data: mockModelConfigsWithUnconfiguredDefaults, total: mockModelConfigsWithUnconfiguredDefaults.length });
                }),
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const modelsTab = await canvas.findByRole("tab", { name: /Models/i });
        modelsTab.click();

        // Verify default models render with their display names
        await canvas.findByText("General");
        await canvas.findByText("Planning");

        // Verify "Default" badges appear for both default models
        const badges = canvas.getAllByText("Default");
        expect(badges.length).toBeGreaterThanOrEqual(2);

        // Verify "Not configured" text appears for unconfigured models (provider + model columns)
        const notConfiguredTexts = canvas.getAllByText("Not configured");
        expect(notConfiguredTexts.length).toBeGreaterThanOrEqual(2);

        // Verify warning icons are present for unconfigured defaults
        // The AlertTriangle icons have a tooltip; verify they exist via their SVG role
        const warningIcons = canvasElement.querySelectorAll(".text-\\(--warning-wMain\\)");
        expect(warningIcons.length).toBe(2);

        // Verify the configured model (image_gen) does NOT show "Not configured"
        expect(canvas.getByText("Image Gen")).toBeInTheDocument();
        expect(canvas.getByText("dall-e-3")).toBeInTheDocument();
    },
};
