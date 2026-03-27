import { PromptBuilderChat } from "@/lib/components/prompts";
import type { Meta, StoryContext, StoryFn, StoryObj } from "@storybook/react-vite";
import { expect, fireEvent, within } from "storybook/test";
import { http, HttpResponse } from "msw";
import { fn } from "storybook/test";

// ── MSW Handlers ────────────────────────────────────────────────────────────

const initHandler = http.get("*/api/v1/prompts/chat/init", () => {
    return HttpResponse.json({
        message: "Hi! I'll help you create a prompt template. What kind of task would you like to template?",
    });
});

const successHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "I'll create a code review template for you. What information changes each time?",
        template_updates: { name: "Code Review Template", category: "Development" },
        confidence: 0.8,
        ready_to_save: false,
        is_error: false,
    });
});

const authErrorHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "The LLM service rejected the authentication credentials. Contact an administrator to verify the API key or authentication configuration.",
        template_updates: {},
        confidence: 0.0,
        ready_to_save: false,
        is_error: true,
    });
});

const rateLimitErrorHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "The LLM service rate limit has been exceeded. Wait a moment and try again. If this persists, contact an administrator to review rate limits or adjust the plan.",
        template_updates: {},
        confidence: 0.0,
        ready_to_save: false,
        is_error: true,
    });
});

const timeoutErrorHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "The request to the LLM service timed out. This may be due to high load or a complex request. Try again. If this persists, contact an administrator.",
        template_updates: {},
        confidence: 0.0,
        ready_to_save: false,
        is_error: true,
    });
});

const modelNotFoundErrorHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "The configured LLM model was not found. Contact an administrator to verify the model name and provider configuration.",
        template_updates: {},
        confidence: 0.0,
        ready_to_save: false,
        is_error: true,
    });
});

const connectionErrorHandler = http.post("*/api/v1/prompts/chat", () => {
    return HttpResponse.json({
        message: "Unable to connect to the LLM service. This may be due to a network issue or incorrect endpoint configuration. Contact an administrator to verify the connection settings.",
        template_updates: {},
        confidence: 0.0,
        ready_to_save: false,
        is_error: true,
    });
});

// ── Meta ─────────────────────────────────────────────────────────────────────

const meta = {
    title: "Pages/Prompts/PromptBuilderChat",
    component: PromptBuilderChat,
    parameters: {
        layout: "fullscreen",
        docs: {
            description: {
                component: "AI-assisted prompt builder chat with error state styling. Error messages from the LLM service are displayed with red border, background, and an alert icon.",
            },
        },
        msw: { handlers: [initHandler, successHandler] },
    },
    args: {
        onConfigUpdate: fn(),
        onReadyToSave: fn(),
        currentConfig: {
            name: "",
            description: "",
            category: "",
            command: "",
            promptText: "",
        },
    },
    decorators: [
        (Story: StoryFn, context: StoryContext) => {
            const storyResult = Story(context.args, context);
            return <div style={{ height: "600px", width: "500px", border: "1px solid var(--secondary-w20)", borderRadius: "12px", overflow: "hidden" }}>{storyResult}</div>;
        },
    ],
} satisfies Meta<typeof PromptBuilderChat>;

export default meta;
type Story = StoryObj<typeof PromptBuilderChat>;

// ── Helpers ──────────────────────────────────────────────────────────────────

const USER_PROMPT = "I want a template for weekly code reviews that includes the PR link, reviewer name, and summary of changes.";

/** Type a message into the chat textarea and click Send. */
async function sendMessage(canvas: ReturnType<typeof within>) {
    const textarea = await canvas.findByRole("textbox");
    fireEvent.change(textarea, { target: { value: USER_PROMPT } });

    const sendButton = canvas.getByRole("button", { name: /send message/i });
    fireEvent.click(sendButton);
}

// ── Stories ──────────────────────────────────────────────────────────────────

export const Default: Story = {
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const heading = await canvas.findByText("AI Builder");
        expect(heading).toBeVisible();

        // Greeting message should be visible
        await canvas.findByText(/I'll help you create a prompt template/);

        // Send a message and verify the full round-trip
        await sendMessage(canvas);

        // User message appears in the chat
        await canvas.findByText(USER_PROMPT);

        // Assistant response appears
        const response = await canvas.findByText(/I'll create a code review template for you/);
        expect(response).toBeVisible();

        // Input is cleared and ready for the next message
        const textarea = canvas.getByRole("textbox");
        expect(textarea).toHaveValue("");
        expect(textarea).not.toBeDisabled();
    },
};

export const AuthenticationError: Story = {
    parameters: {
        docs: {
            description: {
                story: "Shows the error state when the LLM service rejects authentication credentials. The error message is displayed with red styling and an alert icon.",
            },
        },
        msw: { handlers: [initHandler, authErrorHandler] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await sendMessage(canvas);

        // Error message appears with alert styling
        const errorMsg = await canvas.findByText(/LLM service rejected the authentication credentials/);
        expect(errorMsg).toBeVisible();

        // User's message is preserved in the chat history
        expect(canvas.getByText(USER_PROMPT)).toBeVisible();

        // Input is re-enabled so user can retry
        const textarea = canvas.getByRole("textbox");
        expect(textarea).not.toBeDisabled();
    },
};

export const RateLimitError: Story = {
    parameters: {
        docs: {
            description: {
                story: "Shows the error state when the LLM rate limit is exceeded.",
            },
        },
        msw: { handlers: [initHandler, rateLimitErrorHandler] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await sendMessage(canvas);

        const errorMsg = await canvas.findByText(/rate limit has been exceeded/);
        expect(errorMsg).toBeVisible();
    },
};

export const TimeoutError: Story = {
    parameters: {
        docs: {
            description: {
                story: "Shows the error state when the LLM request times out.",
            },
        },
        msw: { handlers: [initHandler, timeoutErrorHandler] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await sendMessage(canvas);

        const errorMsg = await canvas.findByText(/request to the LLM service timed out/);
        expect(errorMsg).toBeVisible();
    },
};

export const ModelNotFoundError: Story = {
    parameters: {
        docs: {
            description: {
                story: "Shows the error state when the configured LLM model is not found.",
            },
        },
        msw: { handlers: [initHandler, modelNotFoundErrorHandler] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await sendMessage(canvas);

        const errorMsg = await canvas.findByText(/configured LLM model was not found/);
        expect(errorMsg).toBeVisible();
    },
};

export const ConnectionError: Story = {
    parameters: {
        docs: {
            description: {
                story: "Shows the error state when the LLM service cannot be reached.",
            },
        },
        msw: { handlers: [initHandler, connectionErrorHandler] },
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        await sendMessage(canvas);

        const errorMsg = await canvas.findByText(/Unable to connect to the LLM service/);
        expect(errorMsg).toBeVisible();
    },
};
