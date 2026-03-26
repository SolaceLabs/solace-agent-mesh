/// <reference types="@testing-library/jest-dom" />
import React, { act } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { TooltipProvider } from "@/lib/components/ui/tooltip";
import type { VisualizerStep } from "@/lib/types";

expect.extend(matchers);

// ---- Mocks ----

// Store callbacks so tests can invoke them
let capturedOnNodeClick: ((node: unknown) => void) | undefined;
let capturedOnEdgeClick: ((edge: unknown) => void) | undefined;

const mockFitToContent = vi.fn();
const mockGetTransform = vi.fn().mockReturnValue({ scale: 1, x: 0, y: 0 });

// The component under test uses relative imports from its location (src/lib/components/share/).
// We must mock the modules using the same path format the bundler resolves them to.
// Use the src-relative @/ alias paths which vitest resolves via its alias config.

vi.mock("@/lib/components/activities/FlowChart/PanZoomCanvas", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const R = require("react");
    const PanZoomCanvas = R.forwardRef(function PanZoomCanvas(props: { children: React.ReactNode; onUserInteraction?: () => void }, ref: React.Ref<unknown>) {
        R.useImperativeHandle(ref, () => ({
            fitToContent: mockFitToContent,
            getTransform: mockGetTransform,
            resetTransform: vi.fn(),
            zoomIn: vi.fn(),
            zoomOut: vi.fn(),
        }));
        return R.createElement("div", { "data-testid": "pan-zoom-canvas" }, props.children);
    });
    PanZoomCanvas.displayName = "PanZoomCanvas";
    return { default: PanZoomCanvas };
});

vi.mock("@/lib/components/activities/FlowChart/WorkflowRenderer", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const R = require("react");
    return {
        default: function MockWorkflowRenderer(props: { processedSteps: unknown[]; onNodeClick?: (node: unknown) => void; onEdgeClick?: (edge: unknown) => void; showDetail?: boolean; selectedStepId?: string | null }) {
            capturedOnNodeClick = props.onNodeClick;
            capturedOnEdgeClick = props.onEdgeClick;
            return R.createElement(
                "div",
                {
                    "data-testid": "workflow-renderer",
                    "data-show-detail": String(props.showDetail),
                    "data-selected-step": props.selectedStepId ?? "",
                },
                `${props.processedSteps.length} steps`
            );
        },
    };
});

vi.mock("@/lib/components/activities/FlowChart/NodeDetailsCard", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const R = require("react");
    return {
        default: function MockNodeDetailsCard(props: { nodeDetails: unknown; onClose: () => void }) {
            return R.createElement("div", { "data-testid": "node-details-card" }, R.createElement("button", { "data-testid": "node-details-close", onClick: props.onClose }, "Close"), "Node Details Content");
        },
    };
});

vi.mock("@/lib/components/activities/FlowChart/utils/nodeDetailsHelper", () => ({
    findNodeDetails: vi.fn().mockReturnValue({
        nodeType: "agent",
        label: "MockAgent",
        description: "A mock agent node",
    }),
}));

import { SharedFlowChartPanel } from "@/lib/components/share/SharedFlowChartPanel";

// ---- Helpers ----

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

function renderPanel(steps: VisualizerStep[], agentMap?: Record<string, string>) {
    return render(
        <TooltipProvider>
            <SharedFlowChartPanel processedSteps={steps} agentNameDisplayNameMap={agentMap} />
        </TooltipProvider>
    );
}

// ---- Tests ----

describe("SharedFlowChartPanel", () => {
    beforeEach(() => {
        capturedOnNodeClick = undefined;
        capturedOnEdgeClick = undefined;
        mockFitToContent.mockClear();
        mockGetTransform.mockClear();
    });

    test("renders 'No steps to display' when processedSteps is empty", () => {
        renderPanel([]);
        expect(screen.getByText(/No steps to display/)).toBeInTheDocument();
        expect(screen.queryByTestId("workflow-renderer")).not.toBeInTheDocument();
    });

    test("renders the flow chart when steps are provided", () => {
        const steps = [makeStep(), makeStep({ id: "step-2", title: "Step 2" })];
        renderPanel(steps);
        expect(screen.getByTestId("workflow-renderer")).toBeInTheDocument();
        expect(screen.getByText("2 steps")).toBeInTheDocument();
    });

    test("shows controls bar with center button and detail mode toggle", () => {
        renderPanel([makeStep()]);
        expect(screen.getByRole("button", { name: /center workflow/i })).toBeInTheDocument();
        expect(screen.getByText("Detail Mode")).toBeInTheDocument();
        expect(screen.getByRole("switch")).toBeInTheDocument();
    });

    test("detail mode toggle changes showDetail state", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);

        const renderer = screen.getByTestId("workflow-renderer");
        expect(renderer).toHaveAttribute("data-show-detail", "true");

        const toggle = screen.getByRole("switch");
        await user.click(toggle);

        expect(screen.getByTestId("workflow-renderer")).toHaveAttribute("data-show-detail", "false");
    });

    test("node click opens the details dialog", async () => {
        renderPanel([makeStep()]);

        expect(capturedOnNodeClick).toBeDefined();

        const mockNode = {
            id: "node-1",
            type: "agent" as const,
            data: { label: "AgentNode", visualizerStepId: "step-1" },
            x: 0,
            y: 0,
            width: 100,
            height: 50,
            children: [],
        };

        act(() => {
            capturedOnNodeClick!(mockNode);
        });

        expect(await screen.findByTestId("node-details-card")).toBeInTheDocument();
        expect(screen.getByText("Node Details Content")).toBeInTheDocument();
    });

    test("dialog can be closed via NodeDetailsCard onClose", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);

        const mockNode = {
            id: "node-1",
            type: "agent" as const,
            data: { label: "AgentNode", visualizerStepId: "step-1" },
            x: 0,
            y: 0,
            width: 100,
            height: 50,
            children: [],
        };

        act(() => {
            capturedOnNodeClick!(mockNode);
        });

        const card = await screen.findByTestId("node-details-card");
        expect(card).toBeInTheDocument();

        await user.click(screen.getByTestId("node-details-close"));

        expect(screen.queryByTestId("node-details-card")).not.toBeInTheDocument();
    });

    test("re-center button is clickable", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);

        const centerButton = screen.getByRole("button", { name: /center workflow/i });
        await user.click(centerButton);

        expect(centerButton).toBeInTheDocument();
    });

    test("edge click sets highlighted step", () => {
        renderPanel([makeStep({ id: "step-1" }), makeStep({ id: "step-2", title: "Step 2" })]);

        expect(capturedOnEdgeClick).toBeDefined();

        const mockEdge = {
            id: "edge-1",
            source: "node-1",
            target: "node-2",
            sourceX: 0,
            sourceY: 0,
            targetX: 100,
            targetY: 100,
            visualizerStepId: "step-2",
        };

        act(() => {
            capturedOnEdgeClick!(mockEdge);
        });

        expect(screen.getByTestId("workflow-renderer")).toHaveAttribute("data-selected-step", "step-2");
    });
});
