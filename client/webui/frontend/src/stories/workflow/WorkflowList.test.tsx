/// <reference types="@testing-library/jest-dom" />
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect } from "vitest";
import meta, { Default } from "./WorkflowList.stories";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

describe("WorkflowList", () => {
    describe("Search and Filtering", () => {
        test("filters workflows by search term", async () => {
            const DefaultStory = composeStory(Default, meta);
            render(<DefaultStory />);
            const user = userEvent.setup();

            // Type in search input
            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "Complete");

            // Verify filtered results
            expect(await screen.findByText("Complete Order Workflow")).toBeInTheDocument();
            expect(screen.queryByText("SimpleLoopWorkflow")).not.toBeInTheDocument();
        });

        test("shows empty state for non-matching search", async () => {
            const DefaultStory = composeStory(Default, meta);
            render(<DefaultStory />);
            const user = userEvent.setup();

            // Search for non-existent workflow
            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "NONEXISTENT123");

            // Verify empty state
            expect(await screen.findByText("No workflows found")).toBeInTheDocument();
            expect(screen.queryByRole("table", { name: "Workflows" })).not.toBeInTheDocument();
        });

        test("clears search filter and restores all workflows", async () => {
            const DefaultStory = composeStory(Default, meta);
            render(<DefaultStory />);
            const user = userEvent.setup();

            // Get initial workflow count
            const table = await screen.findByRole("table", { name: "Workflows" });
            const initialRows = within(table).getAllByRole("row");
            const initialCount = initialRows.length - 1; // Subtract header row

            // Search for non-matching term
            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "NONEXISTENT");

            // Verify no results
            expect(screen.queryByRole("table", { name: "Workflows" })).not.toBeInTheDocument();

            // Click Clear Filter button
            const clearButton = await screen.findByRole("button", { name: "Clear Filter" });
            await user.click(clearButton);

            // Verify all workflows restored
            const restoredTable = await screen.findByRole("table", { name: "Workflows" });
            const restoredRows = within(restoredTable).getAllByRole("row");
            expect(restoredRows.length - 1).toBe(initialCount);
        });

        test("search is case-insensitive", async () => {
            const DefaultStory = composeStory(Default, meta);
            render(<DefaultStory />);
            const user = userEvent.setup();

            // Search with lowercase
            const searchInput = await screen.findByPlaceholderText("Filter by name...");
            await user.type(searchInput, "complete");

            // Verify it still finds Complete Order Workflow
            expect(await screen.findByText("Complete Order Workflow")).toBeInTheDocument();
        });
    });
});
