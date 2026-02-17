/// <reference types="@testing-library/jest-dom" />
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, vi } from "vitest";
import meta, { Default } from "./WorkflowDetailPanel.stories";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

describe("WorkflowDetailPanel", () => {
    describe("Close Button", () => {
        test("calls onClose when close button is clicked", async () => {
            const mockOnClose = vi.fn();
            const Story = composeStory(
                {
                    ...Default,
                    args: {
                        ...Default.args,
                        onClose: mockOnClose,
                    },
                },
                meta
            );
            render(<Story />);
            const user = userEvent.setup();

            // Find and click close button within the panel
            const panel = await screen.findByRole("complementary", { name: "Workflow details panel" });
            const closeButton = within(panel).getByRole("button", { name: "Close" });

            await user.click(closeButton);

            expect(mockOnClose).toHaveBeenCalledTimes(1);
        });
    });
});
