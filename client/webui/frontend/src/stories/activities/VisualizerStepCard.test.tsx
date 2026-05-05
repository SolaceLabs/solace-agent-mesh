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
            response: "I will generate the report now.",
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

const artifactStep = {
    id: "s-artifact",
    type: "AGENT_ARTIFACT_NOTIFICATION" as const,
    timestamp: ts,
    title: "Created Artifact - report.md",
    data: {
        artifactNotification: {
            artifactName: "report.md",
            version: 2,
            mimeType: "text/markdown",
            description: "A generated report",
        },
    },
    ...baseStep,
};

const mockArtifact = {
    filename: "report.md",
    mime_type: "text/markdown",
    size: 1024,
    last_modified: new Date().toISOString(),
    version: 1,
};

describe("VisualizerStepCard View File with custom props", () => {
    test("uses artifactLookup and onViewArtifact when both are provided", async () => {
        const artifactLookup = vi.fn().mockReturnValue(mockArtifact);
        const onViewArtifact = vi.fn();

        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [] }}>
                    <VisualizerStepCard step={artifactStep} artifactLookup={artifactLookup} onViewArtifact={onViewArtifact} />
                </StoryProvider>
            </MemoryRouter>
        );

        await userEvent.setup().click(screen.getByRole("button", { name: "View File" }));

        expect(artifactLookup).toHaveBeenCalledWith("report.md");
        expect(onViewArtifact).toHaveBeenCalledWith(mockArtifact, 2);
    });

    test("passes undefined version when step has no version", async () => {
        const stepNoVersion = {
            ...artifactStep,
            data: {
                artifactNotification: { artifactName: "report.md", mimeType: "text/markdown" },
            },
        };
        const artifactLookup = vi.fn().mockReturnValue(mockArtifact);
        const onViewArtifact = vi.fn();

        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [] }}>
                    <VisualizerStepCard step={stepNoVersion} artifactLookup={artifactLookup} onViewArtifact={onViewArtifact} />
                </StoryProvider>
            </MemoryRouter>
        );

        await userEvent.setup().click(screen.getByRole("button", { name: "View File" }));

        expect(onViewArtifact).toHaveBeenCalledWith(mockArtifact, undefined);
    });

    test("does not call onViewArtifact when artifactLookup returns undefined", async () => {
        const artifactLookup = vi.fn().mockReturnValue(undefined);
        const onViewArtifact = vi.fn();

        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [] }}>
                    <VisualizerStepCard step={artifactStep} artifactLookup={artifactLookup} onViewArtifact={onViewArtifact} />
                </StoryProvider>
            </MemoryRouter>
        );

        await userEvent.setup().click(screen.getByRole("button", { name: "View File" }));

        expect(artifactLookup).toHaveBeenCalledWith("report.md");
        expect(onViewArtifact).not.toHaveBeenCalled();
    });

    test("falls back to ChatContext when props are not provided", async () => {
        const setPreviewArtifact = vi.fn();

        render(
            <MemoryRouter>
                <StoryProvider chatContextValues={{ sessionId: "test", artifacts: [mockArtifact], setPreviewArtifact }}>
                    <VisualizerStepCard step={artifactStep} />
                </StoryProvider>
            </MemoryRouter>
        );

        await userEvent.setup().click(screen.getByRole("button", { name: "View File" }));

        expect(setPreviewArtifact).toHaveBeenCalledWith(mockArtifact);
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
