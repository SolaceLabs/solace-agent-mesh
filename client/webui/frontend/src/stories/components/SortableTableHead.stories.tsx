import type { Meta, StoryObj } from "@storybook/react-vite";
import { within, expect, fn } from "storybook/test";
import { userEvent } from "storybook/test";

import { SortableTableHead } from "@/lib/components/ui";

const meta = {
    title: "Components/SortableTableHead",
    component: SortableTableHead,
    parameters: {
        layout: "centered",
    },
    /**
     * SortableTableHead renders a <th>, which requires a valid table structure.
     * This decorator provides the minimum required ancestor elements.
     */
    decorators: [
        (Story: React.ComponentType) => (
            <table>
                <thead>
                    <tr>
                        <Story />
                    </tr>
                </thead>
            </table>
        ),
    ],
} satisfies Meta<typeof SortableTableHead>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default: column is not the active sort key.
 * Shows the dimmed ChevronsUpDown icon indicating the column is sortable but not currently active.
 */
export const Inactive: Story = {
    args: {
        column: "name",
        currentSortKey: "other",
        sortDir: "asc",
        onSort: fn(),
        children: "Name",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Name")).toBeInTheDocument();
        expect(canvas.getByRole("button")).toBeInTheDocument();
        // Inactive icon has opacity-40
        const svg = canvas.getByRole("button").querySelector("svg");
        expect(svg?.getAttribute("class")).toContain("opacity-40");
    },
};

/**
 * Active Ascending: column is the active sort key sorted A→Z.
 * Shows a ChevronUp icon.
 */
export const ActiveAscending: Story = {
    args: {
        column: "name",
        currentSortKey: "name",
        sortDir: "asc",
        onSort: fn(),
        children: "Name",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        // Active icon must NOT be dimmed
        const svg = canvas.getByRole("button").querySelector("svg");
        expect(svg?.getAttribute("class")).not.toContain("opacity-40");
    },
};

/**
 * Active Descending: column is the active sort key sorted Z→A.
 * Shows a ChevronDown icon.
 */
export const ActiveDescending: Story = {
    args: {
        column: "name",
        currentSortKey: "name",
        sortDir: "desc",
        onSort: fn(),
        children: "Name",
    },
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        const svg = canvas.getByRole("button").querySelector("svg");
        expect(svg?.getAttribute("class")).not.toContain("opacity-40");
    },
};

/**
 * Click fires onSort: verifies the callback is called with the correct column key.
 */
export const ClickCallsOnSort: Story = {
    args: {
        column: "email",
        currentSortKey: "other",
        sortDir: "asc",
        onSort: fn(),
        children: "Email",
    },
    play: async ({ canvasElement, args }) => {
        const canvas = within(canvasElement);
        await userEvent.click(canvas.getByRole("button"));
        expect(args.onSort).toHaveBeenCalledWith("email");
        expect(args.onSort).toHaveBeenCalledTimes(1);
    },
};

/**
 * Multiple columns in a row: one active (Name, asc), two inactive.
 * Renders without the meta decorator to avoid invalid table nesting.
 */
export const MultipleColumns: Story = {
    args: {
        column: "name",
        currentSortKey: "name",
        sortDir: "asc",
        onSort: fn(),
        children: "Name",
    },
    render: () => (
        <table>
            <thead>
                <tr>
                    <SortableTableHead column="name" currentSortKey="name" sortDir="asc" onSort={() => {}}>
                        Name
                    </SortableTableHead>
                    <SortableTableHead column="model" currentSortKey="name" sortDir="asc" onSort={() => {}}>
                        Model
                    </SortableTableHead>
                    <SortableTableHead column="provider" currentSortKey="name" sortDir="asc" onSort={() => {}}>
                        Model Provider
                    </SortableTableHead>
                </tr>
            </thead>
        </table>
    ),
    play: async ({ canvasElement }) => {
        const canvas = within(canvasElement);
        expect(canvas.getByText("Name")).toBeInTheDocument();
        expect(canvas.getByText("Model")).toBeInTheDocument();
        expect(canvas.getByText("Model Provider")).toBeInTheDocument();

        const buttons = canvas.getAllByRole("button");
        expect(buttons).toHaveLength(3);

        // Only the active column (Name) should have a non-dimmed icon
        const nameSvg = buttons[0].querySelector("svg");
        const modelSvg = buttons[1].querySelector("svg");
        expect(nameSvg?.getAttribute("class")).not.toContain("opacity-40");
        expect(modelSvg?.getAttribute("class")).toContain("opacity-40");
    },
};
