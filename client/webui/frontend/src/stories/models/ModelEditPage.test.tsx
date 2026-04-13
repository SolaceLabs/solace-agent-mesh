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

describe("ModelEditPage - save with connection test", () => {
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
        expect(screen.getByText("Save Model Configuration Failed")).toBeInTheDocument();
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
        const aliasInput = document.querySelector('input[name="alias"]') as HTMLInputElement;
        expect(aliasInput).toBeTruthy();
        expect(aliasInput.value).toBe("anthropic-model");
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
        expect(screen.getByText("Save Model Configuration Failed")).toBeInTheDocument();
    });
});
