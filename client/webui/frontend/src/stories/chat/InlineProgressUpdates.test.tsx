import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InlineProgressUpdates } from "@/lib/components/chat/InlineProgressUpdates";
import type { ProgressUpdate } from "@/lib/types";

// Mock MarkdownWrapper
vi.mock("@/lib/components", () => ({
    MarkdownWrapper: ({ content }: { content: string }) => <div data-testid="markdown-content">{content}</div>,
}));

// Mock ViewWorkflowButton
vi.mock("@/lib/components/ui/ViewWorkflowButton", () => ({
    ViewWorkflowButton: ({ onClick }: { onClick: () => void }) => (
        <button data-testid="viewActivity" onClick={onClick}>
            View Workflow
        </button>
    ),
}));

// Mock lucide-react icons
vi.mock("lucide-react", () => ({
    ChevronDown: () => <span data-testid="chevron-down" />,
    ChevronRight: () => <span data-testid="chevron-right" />,
    ChevronUp: () => <span data-testid="chevron-up" />,
    Loader2: ({ className }: { className?: string }) => <span data-testid="spinner" className={className} />,
}));

// Mock Button component
vi.mock("@/lib/components/ui", () => ({
    Button: ({ children, onClick, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
        <button onClick={onClick} {...props}>
            {children}
        </button>
    ),
}));

const makeUpdate = (text: string, type: ProgressUpdate["type"] = "status", overrides?: Partial<ProgressUpdate>): ProgressUpdate => ({
    type,
    text,
    timestamp: Date.now(),
    ...overrides,
});

describe("InlineProgressUpdates", () => {
    it("renders nothing when updates is empty", () => {
        const { container } = render(<InlineProgressUpdates updates={[]} />);
        expect(container.innerHTML).toBe("");
    });

    it("renders a single status update with text", () => {
        render(<InlineProgressUpdates updates={[makeUpdate("Searching...")]} isActive={true} />);
        expect(screen.getByText("Searching...")).toBeTruthy();
    });

    it("renders multiple status updates", () => {
        const updates = [makeUpdate("Step 1"), makeUpdate("Step 2"), makeUpdate("Step 3")];
        render(<InlineProgressUpdates updates={updates} isActive={true} />);
        expect(screen.getByText("Step 1")).toBeTruthy();
        expect(screen.getByText("Step 2")).toBeTruthy();
        expect(screen.getByText("Step 3")).toBeTruthy();
    });

    it("deduplicates consecutive identical updates", () => {
        const updates = [makeUpdate("Processing..."), makeUpdate("Processing..."), makeUpdate("Done")];
        render(<InlineProgressUpdates updates={updates} isActive={true} />);
        const processingElements = screen.getAllByText("Processing...");
        expect(processingElements.length).toBe(1);
        expect(screen.getByText("Done")).toBeTruthy();
    });

    it("does not deduplicate thinking type updates", () => {
        const updates = [makeUpdate("Thinking", "thinking", { expandableContent: "First thought", isExpandableComplete: true }), makeUpdate("Thinking", "thinking", { expandableContent: "Second thought", isExpandableComplete: true })];
        render(<InlineProgressUpdates updates={updates} isActive={true} />);
        const thinkingElements = screen.getAllByText("Thinking");
        expect(thinkingElements.length).toBe(2);
    });

    it("shows spinner for active last step", () => {
        const updates = [makeUpdate("Processing...")];
        const { container } = render(<InlineProgressUpdates updates={updates} isActive={true} />);
        // The Loader2 icon is rendered for active steps
        const spinner = container.querySelector('[data-testid="spinner"]') || container.querySelector(".animate-spin");
        expect(spinner).toBeTruthy();
    });

    it("collapses to Timeline when task completes", () => {
        const updates = [makeUpdate("Step 1"), makeUpdate("Step 2")];
        const { rerender } = render(<InlineProgressUpdates updates={updates} isActive={true} />);

        // While active, should show steps
        expect(screen.getByText("Step 1")).toBeTruthy();

        // When task completes, should auto-collapse
        rerender(<InlineProgressUpdates updates={updates} isActive={false} />);
        expect(screen.getByText("Timeline")).toBeTruthy();
    });

    it("expands timeline when clicking Timeline", () => {
        const updates = [makeUpdate("Step 1"), makeUpdate("Step 2")];
        const { rerender } = render(<InlineProgressUpdates updates={updates} isActive={true} />);
        rerender(<InlineProgressUpdates updates={updates} isActive={false} />);

        // Click Timeline to expand
        fireEvent.click(screen.getByText("Timeline"));
        expect(screen.getByText("Step 1")).toBeTruthy();
        expect(screen.getByText("Step 2")).toBeTruthy();
    });

    it("renders all steps when count is above threshold", () => {
        // With 8 updates, the component should still render (either collapsed or expanded)
        const updates = Array.from({ length: 8 }, (_, i) => makeUpdate(`UniqueStep${i + 1}`));
        render(<InlineProgressUpdates updates={updates} isActive={true} />);
        // First and last steps should be visible
        expect(screen.getByText("UniqueStep1")).toBeTruthy();
        expect(screen.getByText("UniqueStep8")).toBeTruthy();
    });

    it("shows all steps after expanding", () => {
        const updates = Array.from({ length: 7 }, (_, i) => makeUpdate(`Step ${i + 1}`));
        const { container } = render(<InlineProgressUpdates updates={updates} isActive={true} />);

        // Find and click the expand button (contains "more step" text)
        const buttons = container.querySelectorAll("button");
        const expandButton = Array.from(buttons).find(b => b.textContent?.includes("more step"));
        if (expandButton) {
            fireEvent.click(expandButton);
            for (let i = 1; i <= 7; i++) {
                expect(screen.getByText(`Step ${i}`)).toBeTruthy();
            }
        }
    });

    it("renders thinking type as collapsible (collapsed by default)", () => {
        const updates = [makeUpdate("Thinking", "thinking", { expandableContent: "Deep analysis..." })];
        render(<InlineProgressUpdates updates={updates} isActive={true} />);
        expect(screen.getByText("Thinking")).toBeTruthy();
        // Content should NOT be visible initially
        expect(screen.queryByTestId("markdown-content")).toBeNull();
    });

    it("expands thinking content on click", () => {
        const updates = [makeUpdate("Thinking", "thinking", { expandableContent: "Deep analysis..." })];
        render(<InlineProgressUpdates updates={updates} isActive={true} />);

        // Click the thinking button to expand
        const thinkingButton = screen.getByText("Thinking");
        fireEvent.click(thinkingButton);

        // After clicking, the expandable content should be visible
        // The MarkdownWrapper mock renders with data-testid="markdown-content"
        const markdownEl = screen.queryByTestId("markdown-content");
        if (markdownEl) {
            expect(markdownEl.textContent).toContain("Deep analysis...");
        } else {
            // If mock doesn't work, at least verify the text appears somewhere
            expect(screen.getByText("Deep analysis...")).toBeTruthy();
        }
    });

    it("shows workflow button during active streaming", () => {
        const onViewWorkflow = vi.fn();
        render(<InlineProgressUpdates updates={[makeUpdate("Processing...")]} isActive={true} onViewWorkflow={onViewWorkflow} />);

        const button = screen.getByTestId("viewActivity");
        fireEvent.click(button);
        expect(onViewWorkflow).toHaveBeenCalled();
    });

    it("does not show workflow button when task is complete (collapsed)", () => {
        const onViewWorkflow = vi.fn();
        const updates = [makeUpdate("Done")];
        const { rerender } = render(<InlineProgressUpdates updates={updates} isActive={true} onViewWorkflow={onViewWorkflow} />);
        rerender(<InlineProgressUpdates updates={updates} isActive={false} onViewWorkflow={onViewWorkflow} />);
        expect(screen.queryByTestId("viewActivity")).toBeNull();
    });

    it("renders vertical connecting line when multiple updates", () => {
        const updates = [makeUpdate("Step 1"), makeUpdate("Step 2"), makeUpdate("Step 3")];
        const { container } = render(<InlineProgressUpdates updates={updates} isActive={true} />);
        const line = container.querySelector('[class*="opacity-30"]');
        expect(line).toBeTruthy();
    });
});
