/// <reference types="@testing-library/jest-dom" />
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import meta, { Expanded, Collapsed, WithSubmenus } from "./CollapsibleNavigationSidebar.stories";

expect.extend(matchers);

const getToggleButton = () => {
    const chevron = document.querySelector(".lucide-chevron-left, .lucide-chevron-right");
    return chevron?.closest("button") as HTMLButtonElement;
};

beforeEach(() => {
    sessionStorage.clear();
});

describe("CollapsibleNavigationSidebar", () => {
    test("collapses when the toggle button is clicked", async () => {
        const user = userEvent.setup();
        const Story = composeStory(Expanded, meta);
        render(<Story />);

        const sidebar = document.querySelector(".navigation-sidebar")!;
        expect(sidebar).toHaveClass("w-64");

        const toggleButton = getToggleButton();
        expect(toggleButton).toBeInTheDocument();
        await user.click(toggleButton);

        expect(sidebar).toHaveClass("w-16");
    });

    test("expands when the toggle button is clicked", async () => {
        const user = userEvent.setup();
        const Story = composeStory(Collapsed, meta);
        render(<Story />);

        const sidebar = document.querySelector(".navigation-sidebar")!;
        expect(sidebar).toHaveClass("w-16");

        const toggleButton = getToggleButton();
        expect(toggleButton).toBeInTheDocument();
        await user.click(toggleButton);

        expect(sidebar).toHaveClass("w-64");
    });

    test("nav items with routes render as links", async () => {
        const Story = composeStory(Expanded, meta);
        render(<Story />);

        const projectsLink = screen.getByRole("link", { name: /projects/i });
        expect(projectsLink).toHaveAttribute("href", "/projects");

        const agentsLink = screen.getByRole("link", { name: /agents/i });
        expect(agentsLink).toHaveAttribute("href", "/agents");
    });

    test("bottom items without routes render as buttons", async () => {
        const Story = composeStory(Expanded, meta);
        render(<Story />);

        const userAccountButton = screen.getByRole("button", { name: /user account/i });
        expect(userAccountButton).toBeInTheDocument();
        expect(userAccountButton.tagName).toBe("BUTTON");
    });

    test("child items with tooltip show tooltip on hover", async () => {
        const user = userEvent.setup();
        const Story = composeStory(WithSubmenus, meta);
        render(<Story />);

        // Verify submenu children are visible
        const promptsLink = screen.getByRole("link", { name: /prompts/i });
        expect(promptsLink).toBeInTheDocument();

        // Hover over the Prompts nav item to trigger tooltip
        await user.hover(promptsLink);

        // Wait for the tooltip to appear (Radix tooltip has a 500ms delay)
        // Radix renders tooltip content in multiple DOM nodes (visible + accessibility), so use getAllByText
        await waitFor(
            () => {
                const tooltipElements = screen.getAllByText("Experimental Feature");
                expect(tooltipElements.length).toBeGreaterThan(0);
            },
            { timeout: 2000 }
        );

        // Verify the tooltip role element exists
        expect(screen.getByRole("tooltip")).toHaveTextContent("Experimental Feature");
    });

    test("child items with tooltip do not render badge in nav", async () => {
        const Story = composeStory(WithSubmenus, meta);
        render(<Story />);

        // Verify submenu children are visible
        expect(screen.getByText("Prompts")).toBeInTheDocument();
        expect(screen.getByText("Artifacts")).toBeInTheDocument();

        // Verify no EXPERIMENTAL badge is rendered in the nav
        expect(screen.queryByText("EXPERIMENTAL")).not.toBeInTheDocument();
    });
});
