/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ModelEditPage } from "@/lib/components/models";
import { StoryProvider } from "../mocks/StoryProvider";
import { anthropicModelConfig } from "../data/models";

expect.extend(matchers);

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** Handlers shared across all edit-mode tests */
function setupEditHandlers(testConnectionResponse: { success: boolean; message: string }) {
    server.use(
        http.get("*/api/v1/platform/models/:id", ({ params }) => {
            if (params.id === anthropicModelConfig.id) {
                return HttpResponse.json({ data: anthropicModelConfig });
            }
            return HttpResponse.json({ error: "Not found" }, { status: 404 });
        }),
        http.post("*/api/v1/platform/providers/:provider/models", () => {
            return HttpResponse.json({
                data: [
                    { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
                    { id: "claude-3-opus", label: "Claude 3 Opus" },
                ],
            });
        }),
        // Test connection handler (validateOnly=true)
        http.post("*/api/v1/platform/models", ({ request }) => {
            const url = new URL(request.url);
            if (url.searchParams.get("validateOnly") !== "true") return;
            return HttpResponse.json({ data: testConnectionResponse });
        }),
        // Save handler (PATCH for update)
        http.patch("*/api/v1/platform/models/:id", async ({ request }) => {
            const body = (await request.json()) as Record<string, unknown>;
            return HttpResponse.json({
                data: { ...anthropicModelConfig, ...body, updatedTime: Date.now() },
            });
        })
    );
}

/** Handlers for create-mode tests */
function setupCreateHandlers(testConnectionResponse: { success: boolean; message: string }) {
    server.use(
        http.post("*/api/v1/platform/providers/:provider/models", () => {
            return HttpResponse.json({
                data: [
                    { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
                    { id: "claude-3-opus", label: "Claude 3 Opus" },
                ],
            });
        }),
        // Test connection + create handler
        http.post("*/api/v1/platform/models", async ({ request }) => {
            const url = new URL(request.url);
            if (url.searchParams.get("validateOnly") === "true") {
                return HttpResponse.json({ data: testConnectionResponse });
            }
            // Create handler (POST without validateOnly)
            const body = (await request.json()) as Record<string, unknown>;
            return HttpResponse.json(
                {
                    data: {
                        id: "new-model-id",
                        ...body,
                        createdBy: "test-user",
                        updatedBy: "test-user",
                        createdTime: Date.now(),
                        updatedTime: Date.now(),
                    },
                },
                { status: 201 }
            );
        })
    );
}

function renderEditPage() {
    return render(
        <StoryProvider>
            <MemoryRouter initialEntries={[`/models/${anthropicModelConfig.id}/edit`]}>
                <Routes>
                    <Route path="/models/:id/edit" element={<ModelEditPage />} />
                    <Route path="/agents" element={<div>Models List</div>} />
                </Routes>
            </MemoryRouter>
        </StoryProvider>
    );
}

function renderCreatePage() {
    return render(
        <StoryProvider>
            <MemoryRouter initialEntries={["/models/new/edit"]}>
                <Routes>
                    <Route path="/models/new/edit" element={<ModelEditPage />} />
                    <Route path="/agents" element={<div>Models List</div>} />
                </Routes>
            </MemoryRouter>
        </StoryProvider>
    );
}

describe("ModelEditPage - edit mode: save with connection test", () => {
    beforeEach(() => {
        // Default to test success — individual tests override as needed
        setupEditHandlers({ success: true, message: "Connection successful" });
    });

    test("saves directly when connection test passes", async () => {
        renderEditPage();
        const user = userEvent.setup();

        await screen.findAllByText("Edit anthropic-model");

        await user.click(screen.getByRole("button", { name: /Save/i }));

        // Verify no dialog appeared — test passed silently and save proceeded
        await waitFor(() => {
            expect(screen.queryByRole("dialog")).toBeNull();
        });
    });

    test("shows dialog when connection test fails", async () => {
        setupEditHandlers({ success: false, message: "Authentication failed: Invalid API key provided" });
        renderEditPage();
        const user = userEvent.setup();

        await screen.findAllByText("Edit anthropic-model");

        await user.click(screen.getByRole("button", { name: /Save/i }));

        // Verify dialog appeared with error
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(screen.getByText("Connection Test Failed")).toBeInTheDocument();
        expect(screen.getByText(/Authentication failed/i)).toBeInTheDocument();

        // Verify both action buttons
        expect(screen.getByRole("button", { name: /Go Back/i })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Save Anyway/i })).toBeInTheDocument();
    });

    test("closes dialog and preserves form when user clicks Go Back", async () => {
        setupEditHandlers({ success: false, message: "Authentication failed" });
        renderEditPage();
        const user = userEvent.setup();

        await screen.findAllByText("Edit anthropic-model");

        await user.click(screen.getByRole("button", { name: /Save/i }));

        await screen.findByRole("dialog");

        await user.click(screen.getByRole("button", { name: /Go Back/i }));

        // Verify dialog is dismissed and form is still accessible with original values
        await waitFor(() => {
            expect(screen.queryByRole("dialog")).toBeNull();
        });
        expect(screen.getByDisplayValue("anthropic-model")).toBeInTheDocument();
    });

    test("saves when user clicks Save Anyway after test failure", async () => {
        setupEditHandlers({ success: false, message: "Authentication failed" });
        renderEditPage();
        const user = userEvent.setup();

        await screen.findAllByText("Edit anthropic-model");

        await user.click(screen.getByRole("button", { name: /Save/i }));

        await screen.findByRole("dialog");
        await user.click(screen.getByRole("button", { name: /Save Anyway/i }));

        // Verify save proceeded — navigated to models list
        await screen.findByText("Models List");
    });

    test("shows dialog when connection test request throws", async () => {
        // Override the test connection handler to return a network error
        server.use(
            http.post("*/api/v1/platform/models", ({ request }) => {
                const url = new URL(request.url);
                if (url.searchParams.get("validateOnly") !== "true") return;
                return HttpResponse.error();
            })
        );
        renderEditPage();
        const user = userEvent.setup();

        await screen.findAllByText("Edit anthropic-model");

        await user.click(screen.getByRole("button", { name: /Save/i }));

        // Verify dialog appeared
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(screen.getByText("Connection Test Failed")).toBeInTheDocument();
    });
});

/** Fill the create form with valid Anthropic model data */
async function fillCreateForm(user: ReturnType<typeof userEvent.setup>) {
    // Fill alias (find input by name attribute — labels are divs, not <label> elements)
    const aliasInput = document.querySelector('input[name="alias"]') as HTMLInputElement;
    await user.type(aliasInput, "my-new-model");

    // Fill description
    const descInput = document.querySelector('textarea[name="description"]') as HTMLTextAreaElement;
    await user.type(descInput, "A test model for integration");

    // Select provider (Anthropic) — first combobox is the provider selector
    const providerComboboxes = screen.getAllByRole("combobox");
    await user.click(providerComboboxes[0]);
    await user.click(await screen.findByText("Anthropic"));

    // Fill API key (appears after provider selection)
    await waitFor(() => {
        expect(document.querySelector('input[name="apiKey"]')).toBeTruthy();
    });
    const apiKeyInput = document.querySelector('input[name="apiKey"]') as HTMLInputElement;
    await user.type(apiKeyInput, "sk-ant-test-key");

    // Select model name from the combobox
    const modelCombo = await screen.findByPlaceholderText(/Type or select a model/i);
    await user.click(modelCombo);
    await user.click(await screen.findByText("claude-3-5-sonnet"));
}

describe("ModelEditPage - create mode: save with connection test", () => {
    beforeEach(() => {
        setupCreateHandlers({ success: true, message: "Connection successful" });
    });

    test("saves directly when connection test passes in create mode", async () => {
        renderCreatePage();
        const user = userEvent.setup();

        await screen.findAllByText("Add Model");
        await fillCreateForm(user);

        await user.click(screen.getByRole("button", { name: /Add/i }));

        // Verify no dialog — test passed silently and create proceeded
        await waitFor(() => {
            expect(screen.queryByRole("dialog")).toBeNull();
        });

        // Verify navigated to models list
        await screen.findByText("Models List");
    });

    test("shows dialog when connection test fails in create mode", async () => {
        setupCreateHandlers({ success: false, message: "Invalid credentials" });
        renderCreatePage();
        const user = userEvent.setup();

        await screen.findAllByText("Add Model");
        await fillCreateForm(user);

        await user.click(screen.getByRole("button", { name: /Add/i }));

        // Verify dialog appeared
        const dialog = await screen.findByRole("dialog");
        expect(dialog).toBeInTheDocument();
        expect(screen.getByText("Connection Test Failed")).toBeInTheDocument();
        expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument();
    });
});
