import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, screen, within, userEvent } from "storybook/test";
import { http, HttpResponse, delay } from "msw";

import { ModelEditPage } from "@/lib/components/models";
import { anthropicModelConfig, mockModelConfigs } from "../data/models";
import { InvalidateModelCacheDecorator } from "../decorators/InvalidateModelCacheDecorator";

/**
 * Mock handlers for successful API responses when creating a new model
 */
const createNewModelHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: mockModelConfigs, total: mockModelConfigs.length });
    }),
    http.get("*/api/v1/platform/models/supported-by-provider", () => {
        return HttpResponse.json({
            data: [
                { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
                { id: "claude-3-opus", label: "Claude 3 Opus" },
                { id: "claude-3-haiku", label: "Claude 3 Haiku" },
            ],
        });
    }),
    http.post("*/api/v1/platform/models", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
            {
                id: "new-model",
                alias: body.alias,
                ...body,
                createdBy: "test-user",
                updatedBy: "test-user",
                createdTime: Date.now(),
                updatedTime: Date.now(),
            },
            { status: 201 }
        );
    }),
];

/**
 * Mock handlers for editing an existing model
 */
const editModelHandlers = [
    http.get("*/api/v1/platform/models", () => {
        return HttpResponse.json({ data: [anthropicModelConfig], total: 1 });
    }),
    http.get("*/api/v1/platform/models/:alias", ({ params }) => {
        if (params.alias === "anthropic-model") {
            return HttpResponse.json({ data: anthropicModelConfig });
        }
        return HttpResponse.json({ error: "Not found" }, { status: 404 });
    }),
    http.get("*/api/v1/platform/models/supported-by-provider", () => {
        return HttpResponse.json({
            data: [
                { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
                { id: "claude-3-opus", label: "Claude 3 Opus" },
                { id: "claude-3-haiku", label: "Claude 3 Haiku" },
            ],
        });
    }),
    http.put("*/api/v1/platform/models/:alias", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
            ...anthropicModelConfig,
            ...body,
            updatedBy: "test-user",
            updatedTime: Date.now(),
        });
    }),
];

/**
 * Mock handlers for model loading state
 */
const loadingHandlers = [
    http.get("*/api/v1/platform/models/:alias", async () => {
        await delay("infinite");
        return HttpResponse.json({ data: {} });
    }),
];

/**
 * Mock handlers for error state when fetching model for edit
 */
const notFoundHandlers = [
    http.get("*/api/v1/platform/models/:alias", () => {
        return HttpResponse.json({ error: "Model not found" }, { status: 404 });
    }),
];

const meta = {
    title: "Pages/Models/ModelEditPage",
    component: ModelEditPage,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "Form for creating or editing model configurations with provider selection, authentication setup, and advanced parameters.",
            },
        },
    },
    decorators: [
        InvalidateModelCacheDecorator,
        Story => (
            <div style={{ height: "100vh", width: "100vw" }}>
                <Story />
            </div>
        ),
    ],
} satisfies Meta<typeof ModelEditPage>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default story: Creating a new model
 * Shows the form in create mode with empty fields
 */
export const CreateNewModel: Story = {
    parameters: {
        msw: { handlers: createNewModelHandlers },
        routerValues: {
            initialPath: "/models/new/edit",
            routePath: "/models/new/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify we're in create mode by checking the title
        await expect(await canvas.findByText("Create Model")).toBeInTheDocument();

        // Verify form fields are present
        await expect(canvas.getByLabelText(/Display Name/i)).toBeInTheDocument();
        await expect(canvas.getByLabelText(/Description/i)).toBeInTheDocument();
        await expect(canvas.getByLabelText(/Model Provider/i)).toBeInTheDocument();
        await expect(canvas.getByLabelText(/Model Name/i)).toBeInTheDocument();

        // Verify buttons
        const addButton = await canvas.findByRole("button", { name: /Add/i });
        expect(addButton).toBeDisabled(); // Should be disabled until form is filled
    },
};

/**
 * Story: Creating a new Anthropic model with API Key auth
 * Demonstrates filling out the form and creating a model
 */
export const CreateAnthropicModel: Story = {
    parameters: {
        msw: { handlers: createNewModelHandlers },
        routerValues: {
            initialPath: "/models/new/edit",
            routePath: "/models/new/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Fill in Display Name
        const aliasInput = await canvas.findByLabelText(/Display Name/i);
        await userEvent.clear(aliasInput);
        await userEvent.type(aliasInput, "my-planning-model");

        // Fill in Description
        const descInput = await canvas.findByLabelText(/Description/i);
        await userEvent.clear(descInput);
        await userEvent.type(descInput, "Custom planning model for complex reasoning tasks");

        // Select provider
        const providerButton = await canvas.findByRole("button", { name: /Select a provider/i });
        await userEvent.click(providerButton);

        const anthropicOption = await screen.findByText("Anthropic");
        await userEvent.click(anthropicOption);

        // Wait for auth type to appear
        await expect(await canvas.findByLabelText(/Authentication Type/i)).toBeInTheDocument();

        // Fill in API Key
        const apiKeyInputs = await canvas.findAllByLabelText(/API Key/i);
        const apiKeyInput = apiKeyInputs[0];
        await userEvent.type(apiKeyInput, "sk-ant-test-key-123456");

        // Select model name - should enable model dropdown after API key is filled
        const modelNameCombo = await canvas.findByPlaceholderText(/Type or select a model/i);
        await userEvent.click(modelNameCombo);
        await expect(await canvas.findByText("Claude 3.5 Sonnet")).toBeInTheDocument();
    },
};

/**
 * Story: Editing an existing model
 * Shows a model loaded in edit mode with populated fields
 */
export const EditExistingModel: Story = {
    parameters: {
        msw: { handlers: editModelHandlers },
        routerValues: {
            initialPath: "/models/anthropic-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Wait for model to load
        await expect(await canvas.findByText("Edit anthropic-model")).toBeInTheDocument();

        // Verify form fields are populated with existing data
        const aliasInput = (await canvas.findByLabelText(/Display Name/i)) as HTMLInputElement;
        expect(aliasInput.value).toBe("anthropic-model");

        const descInput = (await canvas.findByLabelText(/Description/i)) as HTMLTextAreaElement;
        expect(descInput.value).toContain("planning model");

        // Verify provider is set
        const providerElement = await canvas.findByText("Anthropic");
        expect(providerElement).toBeInTheDocument();

        // Verify model name is populated
        const modelNameInput = (await canvas.findByDisplayValue(/claude/i)) as HTMLInputElement;
        expect(modelNameInput.value).toBe("claude-3-5-sonnet");

        // Verify advanced settings section exists
        const advancedSummary = await canvas.findByText("Advanced Settings");
        expect(advancedSummary).toBeInTheDocument();
    },
};

/**
 * Story: Editing a model in loading state
 * Shows the loading spinner while fetching the model
 */
export const EditModelLoading: Story = {
    parameters: {
        msw: { handlers: loadingHandlers },
        routerValues: {
            initialPath: "/models/some-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify loading state is shown
        await expect(await canvas.findByText("Loading Model...")).toBeInTheDocument();
    },
};

/**
 * Story: Attempting to edit a model that doesn't exist
 * Shows the not found error state
 */
export const EditModelNotFound: Story = {
    parameters: {
        msw: { handlers: notFoundHandlers },
        routerValues: {
            initialPath: "/models/nonexistent-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Verify error state is shown
        await expect(await canvas.findByText("Model Not Found")).toBeInTheDocument();

        // Verify the Go To Models button is present
        const goToButton = await canvas.findByRole("button", { name: /Go To Models/i });
        expect(goToButton).toBeInTheDocument();
    },
};

/**
 * Story: Edit model with temperature and max tokens advanced parameters
 * Shows the advanced settings expanded with common parameters
 */
export const EditModelWithAdvancedParams: Story = {
    parameters: {
        msw: { handlers: editModelHandlers },
        routerValues: {
            initialPath: "/models/anthropic-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Wait for model to load
        await expect(await canvas.findByText("Edit anthropic-model")).toBeInTheDocument();

        // Open Advanced Settings
        const advancedSummary = await canvas.findByText("Advanced Settings");
        const detailsElement = advancedSummary.closest("details");
        expect(detailsElement).not.toHaveAttribute("open");

        await userEvent.click(advancedSummary);

        // Verify advanced parameters are visible
        const temperatureInput = await canvas.findByLabelText(/Temperature/i);
        expect(temperatureInput).toBeInTheDocument();

        const maxTokensInput = await canvas.findByLabelText(/Max Tokens/i);
        expect(maxTokensInput).toBeInTheDocument();

        // Verify values are populated from model
        expect((temperatureInput as HTMLInputElement).value).toBe("0.1");
        expect((maxTokensInput as HTMLInputElement).value).toBe("4096");
    },
};

/**
 * Story: Create model with Custom provider
 * Shows the form for OpenAI-compatible custom providers
 */
export const CreateCustomProviderModel: Story = {
    parameters: {
        msw: { handlers: createNewModelHandlers },
        routerValues: {
            initialPath: "/models/new/edit",
            routePath: "/models/new/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Fill basic fields
        const aliasInput = await canvas.findByLabelText(/Display Name/i);
        await userEvent.type(aliasInput, "custom-llm");

        const descInput = await canvas.findByLabelText(/Description/i);
        await userEvent.type(descInput, "Custom OpenAI-compatible provider");

        // Select Custom provider
        const providerButton = await canvas.findByRole("button", { name: /Select a provider/i });
        await userEvent.click(providerButton);

        const customOption = await screen.findByText("Custom");
        await userEvent.click(customOption);

        // Verify API Base URL field appears for custom provider
        const apiBaseInput = await canvas.findByLabelText(/API Base URL/i);
        expect(apiBaseInput).toBeInTheDocument();

        await userEvent.type(apiBaseInput, "https://my-api.example.com");
    },
};
