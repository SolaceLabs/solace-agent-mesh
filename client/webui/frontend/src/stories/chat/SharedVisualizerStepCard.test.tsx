/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { SharedVisualizerStepCard } from "@/lib/components/share/SharedVisualizerStepCard";
import { TooltipProvider } from "@/lib/components/ui/tooltip";
import type { VisualizerStep } from "@/lib/types";

expect.extend(matchers);

// Mock MarkdownHTMLConverter to render children as plain text
vi.mock("@/lib/components", () => ({
    MarkdownHTMLConverter: ({ children }: { children: string }) => <div data-testid="markdown-html">{children}</div>,
    JSONViewer: ({ data }: { data: unknown }) => <pre data-testid="json-viewer">{JSON.stringify(data)}</pre>,
}));

vi.mock("@/lib/components/research", () => ({
    ImageSearchGrid: () => <div data-testid="image-search-grid" />,
}));

function makeStep(overrides: Partial<VisualizerStep> = {}): VisualizerStep {
    return {
        id: "step-1",
        type: "USER_REQUEST",
        timestamp: "2025-01-15T10:30:45.123Z",
        title: "Test Step",
        data: {},
        rawEventIds: ["evt-1"],
        nestingLevel: 0,
        owningTaskId: "task-1",
        ...overrides,
    };
}

function renderCard(step: VisualizerStep, props: Partial<Parameters<typeof SharedVisualizerStepCard>[0]> = {}) {
    return render(
        <TooltipProvider>
            <SharedVisualizerStepCard step={step} {...props} />
        </TooltipProvider>
    );
}

describe("SharedVisualizerStepCard", () => {
    test("USER_REQUEST shows step title", () => {
        const step = makeStep({ type: "USER_REQUEST", title: "User Input" });
        renderCard(step);
        expect(screen.getByText("User Input")).toBeInTheDocument();
    });

    test("TASK_COMPLETED shows step title and default message when no finalMessage", () => {
        const step = makeStep({ type: "TASK_COMPLETED", title: "Task Done" });
        renderCard(step);
        expect(screen.getByText("Task Done")).toBeInTheDocument();
        expect(screen.getByText("Task completed successfully.")).toBeInTheDocument();
    });

    test("TASK_COMPLETED shows finalMessage when present", () => {
        const step = makeStep({
            type: "TASK_COMPLETED",
            title: "Task Done",
            data: { finalMessage: "All good!" },
        });
        renderCard(step);
        expect(screen.getByText("All good!")).toBeInTheDocument();
        expect(screen.queryByText("Task completed successfully.")).not.toBeInTheDocument();
    });

    test("TASK_FAILED shows step title", () => {
        const step = makeStep({ type: "TASK_FAILED", title: "Task Failed" });
        renderCard(step);
        expect(screen.getByText("Task Failed")).toBeInTheDocument();
    });

    test("AGENT_LLM_CALL shows step title", () => {
        const step = makeStep({ type: "AGENT_LLM_CALL", title: "LLM Call to GPT-4" });
        renderCard(step);
        expect(screen.getByText("LLM Call to GPT-4")).toBeInTheDocument();
    });

    test("delegation info renders when present", () => {
        const step = makeStep({
            type: "AGENT_LLM_RESPONSE_TOOL_DECISION",
            title: "Tool Decision",
            delegationInfo: [
                {
                    functionCallId: "fc-1",
                    peerAgentName: "ImageAgent",
                    subTaskId: "sub-task-123456789012345678",
                },
            ],
        });
        renderCard(step);
        // Both "Delegated to: " and "ImageAgent" are in the same span element
        expect(screen.getByText(/Delegated to:.*ImageAgent/)).toBeInTheDocument();
    });

    test("error details render when present", () => {
        const step = makeStep({
            type: "TASK_FAILED",
            title: "Failed Step",
            data: {
                errorDetails: {
                    message: "Something went wrong",
                    code: "ERR_500",
                },
            },
        });
        renderCard(step);
        expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
        expect(screen.getByText(/ERR_500/)).toBeInTheDocument();
    });

    test("text content renders via MarkdownHTMLConverter", () => {
        const step = makeStep({
            type: "USER_REQUEST",
            title: "User Request",
            data: { text: "Hello **world**" },
        });
        renderCard(step);
        expect(screen.getByTestId("markdown-html")).toHaveTextContent("Hello **world**");
    });

    test("popover variant has different styling than list variant", () => {
        const step = makeStep({ type: "USER_REQUEST", title: "PopoverStep" });
        const { container } = renderCard(step, { variant: "popover" });
        // The card div is the direct child of the wrapper
        const cardDiv = container.querySelector("[class*='bg-transparent']");
        expect(cardDiv).toBeInTheDocument();
    });

    test("list variant has border and rounded styling", () => {
        const step = makeStep({ type: "USER_REQUEST", title: "ListStep" });
        const { container } = renderCard(step, { variant: "list" });
        const cardDiv = container.querySelector("[class*='rounded-lg']");
        expect(cardDiv).toBeInTheDocument();
    });

    test("nesting level applies indentation in list variant", () => {
        const step = makeStep({ type: "USER_REQUEST", title: "Nested", nestingLevel: 2 });
        const { container } = renderCard(step, { variant: "list" });
        const cardDiv = container.querySelector("[style*='margin-left: 48px']");
        expect(cardDiv).toBeInTheDocument();
    });

    test("nesting level does not apply indentation in popover variant", () => {
        const step = makeStep({ type: "USER_REQUEST", title: "Nested", nestingLevel: 2 });
        const { container } = renderCard(step, { variant: "popover" });
        const cardDiv = container.querySelector("[style*='margin-left: 48px']");
        expect(cardDiv).not.toBeInTheDocument();
    });

    test("displays formatted timestamp", () => {
        const step = makeStep({ timestamp: "2025-01-15T10:30:45.123Z" });
        renderCard(step);
        // The timestamp should contain the milliseconds portion
        expect(screen.getByText(/\.123$/)).toBeInTheDocument();
    });
});
