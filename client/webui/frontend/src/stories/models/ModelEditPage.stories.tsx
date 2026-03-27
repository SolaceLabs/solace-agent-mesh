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
    http.post("*/api/v1/platform/supported-models", () => {
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
    http.post("*/api/v1/platform/supported-models", () => {
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
 * Mock handler for test connection success
 */
const testConnectionSuccessHandler = http.post("*/api/v1/platform/models/test", () => {
    return HttpResponse.json({ data: { success: true, message: "Connection successful. Model responded with: OK" } });
});

/**
 * Mock handler for test connection failure
 */
const testConnectionFailureHandler = http.post("*/api/v1/platform/models/test", () => {
    return HttpResponse.json({ data: { success: false, message: "Authentication failed: Invalid API key provided" } });
});

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

        // Verify we're in create mode by checking the title (appears in both breadcrumb and title)
        const createModelTexts = await canvas.findAllByText("Create Model");
        expect(createModelTexts.length).toBeGreaterThanOrEqual(1);

        // Verify form fields are present (using text queries since labels are divs, not <label> elements)
        // Model Name and other provider-specific fields only appear after provider selection
        await expect(await canvas.findByText("Display Name")).toBeInTheDocument();
        await expect(await canvas.findByText("Description")).toBeInTheDocument();
        await expect(await canvas.findByText("Model Provider")).toBeInTheDocument();

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

        // Fill in Display Name (find input by name attribute since labels are divs, not <label> elements)
        const aliasInput = canvasElement.querySelector('input[name="alias"]') as HTMLInputElement;
        expect(aliasInput).toBeTruthy();
        await userEvent.clear(aliasInput);
        await userEvent.type(aliasInput, "my-planning-model");

        // Fill in Description
        const descInput = canvasElement.querySelector('textarea[name="description"]') as HTMLTextAreaElement;
        expect(descInput).toBeTruthy();
        await userEvent.clear(descInput);
        await userEvent.type(descInput, "Custom planning model for complex reasoning tasks");

        // Select provider (ProviderSelect is a ComboBox with role="combobox")
        const providerComboboxes = await canvas.findAllByRole("combobox");
        const providerCombobox = providerComboboxes[0]; // Provider is the first combobox
        await userEvent.click(providerCombobox);

        const anthropicOption = await screen.findByText("Anthropic");
        await userEvent.click(anthropicOption);

        // Anthropic only supports apikey auth (single type, no radio buttons shown)
        // Wait for API Key field to appear after provider selection
        const apiKeyInput = await canvas.findByText("API Key");
        expect(apiKeyInput).toBeInTheDocument();

        // Fill in API Key (find password input by name attribute)
        const apiKeyField = canvasElement.querySelector('input[name="apiKey"]') as HTMLInputElement;
        expect(apiKeyField).toBeTruthy();
        await userEvent.type(apiKeyField, "sk-ant-test-key-123456");

        // Select model name - should enable model dropdown after API key is filled
        const modelNameCombo = await canvas.findByPlaceholderText(/Type or select a model/i);
        await userEvent.click(modelNameCombo);
        // Model dropdown shows model IDs (not labels) as display text
        await expect(await canvas.findByText("claude-3-5-sonnet")).toBeInTheDocument();
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

        // Wait for model to load (appears in both breadcrumb and title)
        const editTexts = await canvas.findAllByText("Edit anthropic-model");
        expect(editTexts.length).toBeGreaterThanOrEqual(1);

        // Verify form fields are populated with existing data
        const aliasInput = canvasElement.querySelector('input[name="alias"]') as HTMLInputElement;
        expect(aliasInput).toBeTruthy();
        expect(aliasInput.value).toBe("anthropic-model");

        const descInput = canvasElement.querySelector('textarea[name="description"]') as HTMLTextAreaElement;
        expect(descInput).toBeTruthy();
        expect(descInput.value).toContain("planning model");

        // Verify provider is set (displayed as input value in ComboBox)
        const providerElement = await canvas.findByDisplayValue("Anthropic");
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

        // Wait for model to load (appears in both breadcrumb and title)
        const editTexts = await canvas.findAllByText("Edit anthropic-model");
        expect(editTexts.length).toBeGreaterThanOrEqual(1);

        // Open Advanced Settings
        const advancedSummary = await canvas.findByText("Advanced Settings");
        const detailsElement = advancedSummary.closest("details");
        expect(detailsElement).not.toHaveAttribute("open");

        await userEvent.click(advancedSummary);

        // Verify advanced parameters are visible (find inputs by name attribute)
        const temperatureInput = canvasElement.querySelector('input[name="temperature"]') as HTMLInputElement;
        expect(temperatureInput).toBeTruthy();

        const maxTokensInput = canvasElement.querySelector('input[name="maxTokens"]') as HTMLInputElement;
        expect(maxTokensInput).toBeTruthy();

        // Verify values are populated from model
        expect(temperatureInput.value).toBe("0.1");
        expect(maxTokensInput.value).toBe("4096");
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

        // Fill basic fields (find inputs by name attribute since labels are divs, not <label> elements)
        const aliasInput = canvasElement.querySelector('input[name="alias"]') as HTMLInputElement;
        expect(aliasInput).toBeTruthy();
        await userEvent.type(aliasInput, "custom-llm");

        const descInput = canvasElement.querySelector('textarea[name="description"]') as HTMLTextAreaElement;
        expect(descInput).toBeTruthy();
        await userEvent.type(descInput, "Custom OpenAI-compatible provider");

        // Select Custom provider (ProviderSelect is a ComboBox with role="combobox")
        const providerComboboxes = await canvas.findAllByRole("combobox");
        const providerCombobox = providerComboboxes[0]; // Provider is the first combobox
        await userEvent.click(providerCombobox);

        const customOption = await screen.findByText("Custom");
        await userEvent.click(customOption);

        // Verify API Base URL field appears for custom provider
        const apiBaseInput = canvasElement.querySelector('input[name="apiBase"]') as HTMLInputElement;
        expect(apiBaseInput).toBeTruthy();

        await userEvent.type(apiBaseInput, "https://my-api.example.com");
    },
};

/**
 * Story: Test connection succeeds on an existing model
 * Clicks Test Connection and verifies the success banner appears
 */
export const TestConnectionSuccess: Story = {
    parameters: {
        msw: { handlers: [...editModelHandlers, testConnectionSuccessHandler] },
        routerValues: {
            initialPath: "/models/anthropic-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Wait for model to load
        await canvas.findAllByText("Edit anthropic-model");

        // The Test Connection button should be present and enabled (provider + auth + model are set)
        const testButton = await canvas.findByRole("button", { name: /Test Connection/i });
        expect(testButton).toBeInTheDocument();
        expect(testButton).not.toBeDisabled();

        // Click Test Connection
        await userEvent.click(testButton);

        // Verify success banner appears
        const banner = await canvas.findByText(/Connection successful/i);
        expect(banner).toBeInTheDocument();
    },
};

/**
 * Story: Test connection fails on an existing model
 * Clicks Test Connection and verifies the error banner appears
 */
export const TestConnectionFailure: Story = {
    parameters: {
        msw: { handlers: [...editModelHandlers, testConnectionFailureHandler] },
        routerValues: {
            initialPath: "/models/anthropic-model/edit",
            routePath: "/models/:alias/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // Wait for model to load
        await canvas.findAllByText("Edit anthropic-model");

        // Click Test Connection
        const testButton = await canvas.findByRole("button", { name: /Test Connection/i });
        await userEvent.click(testButton);

        // Verify error banner appears
        const banner = await canvas.findByText(/Authentication failed/i);
        expect(banner).toBeInTheDocument();
    },
};

/**
 * Story: Test Connection button is disabled when required fields are missing
 * In create mode without provider/auth/model configured
 */
export const TestConnectionButtonDisabled: Story = {
    parameters: {
        msw: { handlers: createNewModelHandlers },
        routerValues: {
            initialPath: "/models/new/edit",
            routePath: "/models/new/edit",
        },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);

        // In create mode, Test Connection button should not be visible yet
        // (it only appears after provider selection reveals the full form)
        await canvas.findAllByText("Create Model");

        // Select a provider to make the button appear
        const providerComboboxes = await canvas.findAllByRole("combobox");
        await userEvent.click(providerComboboxes[0]);
        const anthropicOption = await screen.findByText("Anthropic");
        await userEvent.click(anthropicOption);

        // Test Connection button should now be visible but disabled (no auth or model yet)
        const testButton = await canvas.findByRole("button", { name: /Test Connection/i });
        expect(testButton).toBeDisabled();
    },
};
