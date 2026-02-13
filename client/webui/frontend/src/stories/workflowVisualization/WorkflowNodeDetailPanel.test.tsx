/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect } from "vitest";
import meta, { LoopNode, AgentNode, MapNode, SwitchNode } from "./WorkflowNodeDetailPanel.stories";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

describe("WorkflowNodeDetailPanel", () => {
    describe("View Toggles", () => {
        test("toggles between Details and Code view", async () => {
            const Story = composeStory(AgentNode, meta);
            render(<Story />);
            const user = userEvent.setup();

            // Verify panel renders
            expect(await screen.findByRole("complementary", { name: "Node details panel" })).toBeInTheDocument();

            // Verify view toggle buttons
            const detailsButton = screen.getByRole("button", { name: "Details view" });
            const codeButton = screen.getByRole("button", { name: "Code view" });

            expect(detailsButton).toBeInTheDocument();
            expect(codeButton).toBeInTheDocument();

            // Switch to Code view
            await user.click(codeButton);

            // Verify Copy button appears in Code view
            expect(screen.getByTestId("Copy")).toBeInTheDocument();

            // Switch back to Details view
            await user.click(detailsButton);

            // Verify Copy button disappears
            expect(screen.queryByTestId("Copy")).not.toBeInTheDocument();
        });
    });

    describe("Loop Node", () => {
        test("displays loop node properties", async () => {
            const Story = composeStory(LoopNode, meta);
            render(<Story />);

            // Verify loop properties
            expect(await screen.findByText("Max Iterations")).toBeInTheDocument();
            expect(screen.getByText("10")).toBeInTheDocument();
            expect(screen.getByText("Condition")).toBeInTheDocument();
            expect(screen.getByText("Delay")).toBeInTheDocument();
            expect(screen.getByText("5s")).toBeInTheDocument();
        });
    });

    describe("Agent Node", () => {
        test("displays agent node properties", async () => {
            const Story = composeStory(AgentNode, meta);
            render(<Story />);

            // Verify agent name is displayed
            expect(await screen.findByText("OrderValidator")).toBeInTheDocument();
            expect(screen.getByText("validate_order")).toBeInTheDocument();
        });

        test("displays input and output tabs", async () => {
            const Story = composeStory(AgentNode, meta);
            render(<Story />);
            const user = userEvent.setup();

            // Verify Input/Output tabs exist
            const inputTab = await screen.findByRole("tab", { name: "Input" });
            const outputTab = screen.getByRole("tab", { name: "Output" });

            expect(inputTab).toBeInTheDocument();
            expect(outputTab).toBeInTheDocument();

            // Click Output tab
            await user.click(outputTab);

            // Verify Output tab is now selected
            expect(outputTab).toHaveAttribute("aria-selected", "true");
        });
    });

    describe("Map Node", () => {
        test("displays map node properties", async () => {
            const Story = composeStory(MapNode, meta);
            render(<Story />);

            // Verify map properties - panel shows node ID as title
            expect(screen.getAllByText("process_items").length).toBeGreaterThan(0);
            expect(screen.getByText("Items")).toBeInTheDocument();
        });
    });

    describe("Switch Node", () => {
        test("displays switch node cases", async () => {
            const Story = composeStory(SwitchNode, meta);
            render(<Story />);

            // Verify switch properties - panel shows node ID as title
            expect(screen.getAllByText("check_priority").length).toBeGreaterThan(0);
            expect(screen.getByText("Cases")).toBeInTheDocument();
        });
    });
});
