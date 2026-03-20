import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen } from "storybook/test";
import { http, HttpResponse } from "msw";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ModelDetailsPage } from "@/lib/components/models";
import { modelKeys } from "@/lib/api/models";
import { anthropicModelConfig } from "../data/models";

/**
 * Mock model data for stories
 */
const mockModelConfigs = [anthropicModelConfig];

/**
 * Mock handlers for successful API responses
 */
const successHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: mockModelConfigs, total: mockModelConfigs.length });
    }),
];

/**
 * Mock handlers for not found state
 */
const notFoundHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: [], total: 0 });
    }),
];

/**
 * Wrapper that clears cache on mount
 */
const CacheInvalidator: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const queryClient = useQueryClient();

    React.useLayoutEffect(() => {
        queryClient.removeQueries({ queryKey: modelKeys.lists() });
    }, [queryClient]);

    return <>{children}</>;
};

const meta = {
    title: "Pages/Models/ModelDetailsPage",
    component: ModelDetailsPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Detailed view of a single model configuration showing authentication type, parameters, and metadata.",
            },
        },
    },
    decorators: [
        Story => (
            <CacheInvalidator>
                <div style={{ height: "100vh", width: "100vw" }}>
                    <Story />
                </div>
            </CacheInvalidator>
        ),
    ],
} satisfies Meta<typeof ModelDetailsPage>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default story showing a model with API Key authentication
 */
export const WithAPIKeyAuth: Story = {
    parameters: {
        msw: { handlers: successHandlers },
        routerValues: {
            initialPath: "/models/anthropic-model",
            routePath: "/models/:alias",
        },
    },
    play: async () => {
        // Model alias displayed in header and breadcrumb
        const aliasElements = await screen.findAllByText("anthropic-model");
        await expect(aliasElements.length).toBeGreaterThan(0);

        // Provider shown with display name
        await expect(await screen.findByText("Anthropic")).toBeInTheDocument();

        // Model name
        await expect(await screen.findByText("claude-3-5-sonnet")).toBeInTheDocument();

        // Description
        await expect(await screen.findByText("Enterprise-grade planning model with prompt caching for cost optimization")).toBeInTheDocument();

        // Auth type rendered as human-readable label
        await expect(await screen.findByText("API Key")).toBeInTheDocument();

        // API base URL
        await expect(await screen.findByText("https://api.anthropic.com")).toBeInTheDocument();

        // Model parameters
        await expect(await screen.findByText("temperature:")).toBeInTheDocument();
        await expect(await screen.findByText("max_tokens:")).toBeInTheDocument();

        // Metadata section
        await expect(await screen.findByText("Metadata")).toBeInTheDocument();
    },
};

/**
 * Story showing model not found state
 */
export const NotFound: Story = {
    parameters: {
        msw: { handlers: notFoundHandlers },
        routerValues: {
            initialPath: "/models/nonexistent-model",
            routePath: "/models/:alias",
        },
    },
    play: async () => {
        await expect(await screen.findByText("Model Not Found")).toBeInTheDocument();
        await expect(await screen.findByRole("button", { name: "Go To Models" })).toBeInTheDocument();
    },
};
