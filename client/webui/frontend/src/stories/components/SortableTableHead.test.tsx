/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { SortableTableHead } from "@/lib/components/ui";

expect.extend(matchers);

/** Wraps content in valid table structure so <th> renders without browser warnings. */
function renderInTable(ui: React.ReactNode) {
    return render(
        <table>
            <thead>
                <tr>{ui}</tr>
            </thead>
        </table>
    );
}

const baseProps = {
    column: "name",
    currentSortKey: "other",
    sortDir: "asc" as const,
    onSort: vi.fn(),
};

beforeEach(() => {
    vi.clearAllMocks();
});

describe("SortableTableHead", () => {
    test("renders the column label", () => {
        renderInTable(<SortableTableHead {...baseProps}>Name</SortableTableHead>);
        expect(screen.getByText("Name")).toBeInTheDocument();
    });

    test("renders a clickable button", () => {
        renderInTable(<SortableTableHead {...baseProps}>Name</SortableTableHead>);
        expect(screen.getByRole("button")).toBeInTheDocument();
    });

    test("renders as a columnheader cell", () => {
        renderInTable(<SortableTableHead {...baseProps}>Name</SortableTableHead>);
        expect(screen.getByRole("columnheader")).toBeInTheDocument();
    });

    test("calls onSort with the column key when clicked", () => {
        const onSort = vi.fn();
        renderInTable(<SortableTableHead {...baseProps} onSort={onSort}>Name</SortableTableHead>);
        fireEvent.click(screen.getByRole("button"));
        expect(onSort).toHaveBeenCalledWith("name");
        expect(onSort).toHaveBeenCalledTimes(1);
    });

    test("passes the correct column key even when children differ from column", () => {
        const onSort = vi.fn();
        renderInTable(
            <SortableTableHead {...baseProps} column="modelName" onSort={onSort}>
                Model
            </SortableTableHead>
        );
        fireEvent.click(screen.getByRole("button"));
        expect(onSort).toHaveBeenCalledWith("modelName");
    });

    test("renders one sort icon when inactive", () => {
        renderInTable(<SortableTableHead {...baseProps} currentSortKey="other">Name</SortableTableHead>);
        const svgs = screen.getByRole("button").querySelectorAll("svg");
        expect(svgs).toHaveLength(1);
    });

    test("renders one sort icon when active ascending", () => {
        renderInTable(
            <SortableTableHead {...baseProps} currentSortKey="name" sortDir="asc">
                Name
            </SortableTableHead>
        );
        const svgs = screen.getByRole("button").querySelectorAll("svg");
        expect(svgs).toHaveLength(1);
    });

    test("renders one sort icon when active descending", () => {
        renderInTable(
            <SortableTableHead {...baseProps} currentSortKey="name" sortDir="desc">
                Name
            </SortableTableHead>
        );
        const svgs = screen.getByRole("button").querySelectorAll("svg");
        expect(svgs).toHaveLength(1);
    });

    test("inactive icon has opacity-40 class (dimmed)", () => {
        renderInTable(<SortableTableHead {...baseProps} currentSortKey="other">Name</SortableTableHead>);
        const svg = screen.getByRole("button").querySelector("svg");
        expect(svg?.getAttribute("class")).toContain("opacity-40");
    });

    test("active icon does not have opacity-40 class", () => {
        renderInTable(
            <SortableTableHead {...baseProps} currentSortKey="name" sortDir="asc">
                Name
            </SortableTableHead>
        );
        const svg = screen.getByRole("button").querySelector("svg");
        expect(svg?.getAttribute("class")).not.toContain("opacity-40");
    });

    test("forwards className to the th element", () => {
        renderInTable(
            <SortableTableHead {...baseProps} className="custom-class">
                Name
            </SortableTableHead>
        );
        const th = screen.getByRole("columnheader");
        expect(th.className).toContain("custom-class");
    });

    test("includes font-semibold by default", () => {
        renderInTable(<SortableTableHead {...baseProps}>Name</SortableTableHead>);
        const th = screen.getByRole("columnheader");
        expect(th.className).toContain("font-semibold");
    });
});
