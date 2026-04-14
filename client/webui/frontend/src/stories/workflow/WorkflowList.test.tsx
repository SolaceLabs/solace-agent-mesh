/// <reference types="@testing-library/jest-dom" />
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { WorkflowList } from "@/lib/components/workflows/WorkflowList";
import { mockWorkflows } from "../data/workflows";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

beforeEach(() => {
    // Mock fetch to return workflow agent cards
    vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
        if (url.includes("/api/v1/agentCards")) {
            return new Response(JSON.stringify(mockWorkflows), {
                status: 200,
                headers: { "Content-Type": "application/json" },
            });
        }
        return new Response("Not found", { status: 404 });
    });
});

function renderWorkflowList() {
    return render(
        <MemoryRouter>
            <StoryProvider>
                <WorkflowList />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("WorkflowList", () => {
    describe("Search and Filtering", () => {
        test("filters workflows by search term", async () => {
            renderWorkflowList();
            const user = userEvent.setup();

            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "Complete");

            expect(await screen.findByText("Complete Order Workflow")).toBeInTheDocument();
            expect(screen.queryByText("SimpleLoopWorkflow")).not.toBeInTheDocument();
        });

        test("shows empty state for non-matching search", async () => {
            renderWorkflowList();
            const user = userEvent.setup();

            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "NONEXISTENT123");

            expect(await screen.findByText("No workflows found")).toBeInTheDocument();
            expect(screen.queryByRole("table", { name: "Workflows" })).not.toBeInTheDocument();
        });

        test("clears search filter and restores all workflows", async () => {
            renderWorkflowList();
            const user = userEvent.setup();

            const table = await screen.findByRole("table", { name: "Workflows" });
            const initialRows = within(table).getAllByRole("row");
            const initialCount = initialRows.length - 1;

            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "NONEXISTENT");

            expect(screen.queryByRole("table", { name: "Workflows" })).not.toBeInTheDocument();

            const clearButton = await screen.findByRole("button", { name: "Clear Filter" });
            await user.click(clearButton);

            const restoredTable = await screen.findByRole("table", { name: "Workflows" });
            const restoredRows = within(restoredTable).getAllByRole("row");
            expect(restoredRows.length - 1).toBe(initialCount);
        });

        test("search is case-insensitive", async () => {
            renderWorkflowList();
            const user = userEvent.setup();

            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "complete");

            expect(await screen.findByText("Complete Order Workflow")).toBeInTheDocument();
        });
    });
});
