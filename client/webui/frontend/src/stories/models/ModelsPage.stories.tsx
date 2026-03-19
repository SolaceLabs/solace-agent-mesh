import type { Meta, StoryObj } from "@storybook/react-vite";
import { within, expect } from "storybook/test";
import { http, HttpResponse, delay } from "msw";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AgentMeshPage } from "@/lib/components/pages";
import { modelKeys } from "@/lib/api/models";
import { mockModelConfigs } from "../data/models";
import { createOpenFeatureDecorator } from "../mocks/OpenFeatureDecorator";

const OpenFeatureDecorator = createOpenFeatureDecorator({ flags: { model_config_ui: true } });

const InvalidateCacheDecorator = (Story: React.ComponentType) => {
    const queryClient = useQueryClient();

    React.useLayoutEffect(() => {
        queryClient.removeQueries({ queryKey: modelKeys.lists() });
    }, [queryClient]);

    return <Story />;
};

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
        InvalidateCacheDecorator,
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

        // Verify table renders with data
        await canvas.findByText("planning");
        await canvas.findByText("general");
        await canvas.findByText("image_gen");

        // Verify columns exist
        expect(canvas.getByText("Name")).toBeInTheDocument();
        expect(canvas.getByText("Model")).toBeInTheDocument();
        expect(canvas.getByText("Model Provider")).toBeInTheDocument();

        // Verify pagination controls don't show (only 8 models fit on one page)
        expect(canvas.queryByRole("navigation", { name: /pagination/i })).not.toBeInTheDocument();
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
        await canvas.findByText("model-0");
        await canvas.findByText("model-19");
        expect(canvas.getByText("model-0")).toBeInTheDocument();

        // Verify pagination controls ARE visible (45 models exceed one page)
        const paginationNav = canvas.getByRole("navigation", { name: /pagination/i });
        expect(paginationNav).toBeInTheDocument();
    },
};
