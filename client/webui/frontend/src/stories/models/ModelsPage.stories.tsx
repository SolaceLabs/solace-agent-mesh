import type { Meta, StoryObj } from "@storybook/react-vite";
import { within } from "storybook/test";
import { http, HttpResponse, delay } from "msw";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AgentMeshPage } from "@/lib/components/pages";
import { modelKeys } from "@/lib/api/models";

const InvalidateCacheDecorator = (Story: React.ComponentType) => {
    const queryClient = useQueryClient();

    React.useLayoutEffect(() => {
        queryClient.removeQueries({ queryKey: modelKeys.lists() });
    }, [queryClient]);

    return <Story />;
};

const mockModelConfigs = [
    {
        id: "1",
        alias: "planning",
        provider: "anthropic",
        modelName: "claude-3-5-sonnet",
        apiBase: "https://api.anthropic.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: { temperature: 0.1, max_tokens: 4096 },
        description: "Planning model for strategic tasks",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "2",
        alias: "general",
        provider: "openai",
        modelName: "gpt-4",
        apiBase: "https://api.openai.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "General purpose model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "3",
        alias: "image_gen",
        provider: "openai",
        modelName: "dall-e-3",
        apiBase: "https://api.openai.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "Image generation model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "4",
        alias: "compatible",
        provider: "openai_compatible",
        modelName: "llama2",
        apiBase: "http://localhost:8000",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "OpenAI-compatible API",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "5",
        alias: "gemini",
        provider: "google_ai_studio",
        modelName: "gemini-2.0-flash",
        apiBase: "https://generativelanguage.googleapis.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "Google AI Studio Gemini model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "6",
        alias: "vertex",
        provider: "vertex_ai",
        modelName: "gemini-1.5-pro",
        apiBase: "https://vertex.googleapis.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "Google Vertex AI model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "7",
        alias: "azure",
        provider: "azure_openai",
        modelName: "gpt-4",
        apiBase: "https://myresource.openai.azure.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "Azure OpenAI deployment",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "8",
        alias: "aws",
        provider: "bedrock",
        modelName: "claude-3-sonnet",
        apiBase: "https://bedrock.amazonaws.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "AWS Bedrock model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "9",
        alias: "local",
        provider: "ollama",
        modelName: "mistral",
        apiBase: "http://localhost:11434",
        hasCredentials: false,
        authType: null,
        modelParams: {},
        description: "Local Ollama model",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
    {
        id: "10",
        alias: "custom_model",
        provider: "custom",
        modelName: "unknown-provider-model",
        apiBase: "https://custom.api.com",
        hasCredentials: true,
        authType: "api_key",
        modelParams: {},
        description: "Custom provider model (fallback icon test)",
        createdBy: "system",
        updatedBy: "system",
        createdTime: Date.now(),
        updatedTime: Date.now(),
    },
];

const successHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: mockModelConfigs });
    }),
];

const loadingHandlers = [
    http.get("*/api/v1/platform/models", async () => {
        await delay("infinite");
        return HttpResponse.json({ data: [] });
    }),
];

const emptyHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: [] });
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
        await canvas.findByRole("tab", { name: /Models/i }).then((tab: HTMLElement) => tab.click());
    },
};

export const Loading: Story = {
    parameters: {
        msw: { handlers: loadingHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByRole("tab", { name: /Models/i }).then((tab: HTMLElement) => tab.click());
    },
};

export const Empty: Story = {
    parameters: {
        msw: { handlers: emptyHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByRole("tab", { name: /Models/i }).then((tab: HTMLElement) => tab.click());
    },
};

export const Error: Story = {
    parameters: {
        msw: { handlers: errorHandlers },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByRole("tab", { name: /Models/i }).then((tab: HTMLElement) => tab.click());
    },
};

export const WithPagination: Story = {
    parameters: {
        msw: {
            handlers: [
                http.get("*/api/v1/platform/models", () => {
                    return HttpResponse.json({
                        data: Array.from({ length: 45 }, (_, i) => ({
                            id: `model-${i}`,
                            alias: `model-${i}`,
                            provider: i % 3 === 0 ? "anthropic" : i % 3 === 1 ? "openai" : "vertex_ai",
                            modelName: `test-model-${i}`,
                            apiBase: "https://api.example.com",
                            hasCredentials: true,
                            authType: "api_key",
                            modelParams: {},
                            description: `Test model ${i}`,
                            createdBy: "system",
                            updatedBy: "system",
                            createdTime: Date.now(),
                            updatedTime: Date.now(),
                        })),
                    });
                }),
            ],
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await canvas.findByRole("tab", { name: /Models/i }).then((tab: HTMLElement) => tab.click());
    },
};
