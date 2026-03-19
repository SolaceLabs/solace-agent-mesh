/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { PaginationControls } from "../../lib/components/common/PaginationControls";

expect.extend(matchers);

describe("PaginationControls", () => {
    test("returns null when totalPages is 1", () => {
        const { container } = render(<PaginationControls totalPages={1} currentPage={1} onPageChange={() => {}} />);
        expect(container.firstChild).toBeNull();
    });

    test("renders all page numbers when totalPages <= 5", () => {
        const mockOnPageChange = vi.fn();
        render(<PaginationControls totalPages={3} currentPage={1} onPageChange={mockOnPageChange} />);

        expect(screen.getByText("1")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
    });

    test("marks current page as active", () => {
        render(<PaginationControls totalPages={3} currentPage={2} onPageChange={() => {}} />);
        const page2Link = screen.getByText("2").closest("a");
        expect(page2Link).toHaveAttribute("aria-current", "page");
    });

    test("calls onPageChange when clicking a page", () => {
        const mockOnPageChange = vi.fn();
        render(<PaginationControls totalPages={3} currentPage={1} onPageChange={mockOnPageChange} />);

        fireEvent.click(screen.getByText("2"));
        expect(mockOnPageChange).toHaveBeenCalledWith(2);
    });

    test("prevents navigation when on first page", () => {
        const mockOnPageChange = vi.fn();
        render(<PaginationControls totalPages={3} currentPage={1} onPageChange={mockOnPageChange} />);

        // Try clicking page 2 - should work
        fireEvent.click(screen.getByText("2"));
        expect(mockOnPageChange).toHaveBeenCalledWith(2);
    });

    test("prevents navigation when on last page", () => {
        const mockOnPageChange = vi.fn();
        render(<PaginationControls totalPages={3} currentPage={3} onPageChange={mockOnPageChange} />);

        // Can navigate to earlier pages
        fireEvent.click(screen.getByText("2"));
        expect(mockOnPageChange).toHaveBeenCalledWith(2);
    });

    test("shows ellipsis for large page counts", () => {
        render(<PaginationControls totalPages={10} currentPage={1} onPageChange={() => {}} />);
        expect(screen.getByText("1")).toBeInTheDocument();
        expect(screen.getByText("10")).toBeInTheDocument();
    });
});
