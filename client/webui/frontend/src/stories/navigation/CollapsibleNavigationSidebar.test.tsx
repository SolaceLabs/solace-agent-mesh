/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { composeStory } from "@storybook/react";
import { describe, test, expect, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import meta, { Expanded, Collapsed } from "./CollapsibleNavigationSidebar.stories";

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

    test("experimental badge renders for prompts and artifacts in expanded sidebar", async () => {
        const Story = composeStory(Expanded, meta);
        render(<Story />);

        const badges = screen.getAllByText("EXPERIMENTAL");
        expect(badges.length).toBeGreaterThanOrEqual(2);
    });
});
