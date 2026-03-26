/// <reference types="@testing-library/jest-dom" />
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { MemoryRouter } from "react-router-dom";

import { VisualizerStepCard } from "@/lib/components/activities/VisualizerStepCard";
import { StoryProvider } from "../mocks/StoryProvider";

expect.extend(matchers);

const ts = new Date().toISOString();
const baseStep = { rawEventIds: [], nestingLevel: 0, owningTaskId: "task-1" };

const llmResponseStep = {
    id: "s-1",
    type: "AGENT_LLM_RESPONSE_TO_AGENT" as const,
    timestamp: ts,
    title: "LLM Response",
    data: {
        llmResponseToAgent: {
            modelName: "gpt-4o",
            responsePreview: "I will generate the report now.",
            isFinalResponse: false,
        },
    },
    ...baseStep,
};

function renderCard(props: Partial<Parameters<typeof VisualizerStepCard>[0]> = {}) {
    return render(
        <MemoryRouter>
            <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [] }}>
                <VisualizerStepCard step={llmResponseStep} {...props} />
            </StoryProvider>
        </MemoryRouter>
    );
}

describe("LLMResponseToAgentDetails expand/collapse (component extracted to module level)", () => {
    test("initially shows collapsed state with 'Show details' button", () => {
        renderCard();
        expect(screen.getByText("Show details")).toBeInTheDocument();
        expect(screen.queryByText("LLM Response Details:")).not.toBeInTheDocument();
    });

    test("clicking 'Show details' expands the detail panel", async () => {
        const user = userEvent.setup();
        renderCard();
        await user.click(screen.getByText("Show details"));
        expect(screen.getByText("LLM Response Details:")).toBeInTheDocument();
        expect(screen.getByText("Hide details")).toBeInTheDocument();
    });

    test("expanded state survives parent re-render (module-level extraction fix)", async () => {
        const user = userEvent.setup();
        const { rerender } = renderCard();
        await user.click(screen.getByText("Show details"));
        expect(screen.getByText("LLM Response Details:")).toBeInTheDocument();

        // Re-render with a different prop — if component was defined inside parent,
        // state would reset and "LLM Response Details:" would disappear
        rerender(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [] }}>
                    <VisualizerStepCard step={llmResponseStep} isHighlighted={true} />
                </StoryProvider>
            </MemoryRouter>
        );

        expect(screen.getByText("LLM Response Details:")).toBeInTheDocument();
    });
});

describe("VisualizerStepCard keyboard accessibility", () => {
    test("pressing Enter calls onClick when provided", () => {
        const onClick = vi.fn();
        renderCard({ onClick });
        // The outermost card div gets role="button" when onClick is provided.
        // Filter to find the div (not the inner <button> elements).
        const cardDiv = screen.getAllByRole("button").find(el => el.tagName === "DIV");
        expect(cardDiv).toBeDefined();
        fireEvent.keyDown(cardDiv!, { key: "Enter" });
        expect(onClick).toHaveBeenCalledTimes(1);
    });

    test("card div has no role=button when onClick is not provided", () => {
        renderCard();
        // The inner "Show details" <button> exists, but the card div should NOT have role="button"
        const divButtons = screen.getAllByRole("button").filter(el => el.tagName === "DIV");
        expect(divButtons).toHaveLength(0);
    });
});
