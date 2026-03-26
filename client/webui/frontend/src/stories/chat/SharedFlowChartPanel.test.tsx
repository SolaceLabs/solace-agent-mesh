/// <reference types="@testing-library/jest-dom" />
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, test, expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import { TooltipProvider } from "@/lib/components/ui/tooltip";
import type { VisualizerStep } from "@/lib/types";

expect.extend(matchers);

// Mock ResizeObserver needed by PanZoomCanvas
vi.stubGlobal(
    "ResizeObserver",
    class {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
);

import { SharedFlowChartPanel } from "@/lib/components/share/SharedFlowChartPanel";

/* ---------- helpers ---------- */

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

/* ---------- tests ---------- */

describe("SharedFlowChartPanel", () => {
    test("renders 'No steps to display' when processedSteps is empty", () => {
        renderPanel([]);
        expect(screen.getByText(/No steps to display/)).toBeInTheDocument();
    });

    test("does not show empty message when steps are provided", () => {
        renderPanel([makeStep()]);
        expect(screen.queryByText(/No steps to display/)).not.toBeInTheDocument();
    });

    test("renders the flow chart container when steps are provided", () => {
        const { container } = renderPanel([makeStep()]);
        const wrapper = container.querySelector("[style*='height: 100%']");
        expect(wrapper).toBeInTheDocument();
    });

    test("shows controls bar with center button and detail mode toggle", () => {
        renderPanel([makeStep()]);
        expect(screen.getByRole("button", { name: /center workflow/i })).toBeInTheDocument();
        expect(screen.getByText("Detail Mode")).toBeInTheDocument();
        expect(screen.getByRole("switch")).toBeInTheDocument();
    });

    test("detail mode toggle is initially checked (on)", () => {
        renderPanel([makeStep()]);
        const toggle = screen.getByRole("switch");
        expect(toggle).toHaveAttribute("aria-checked", "true");
    });

    test("detail mode toggle can be turned off", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);
        const toggle = screen.getByRole("switch");
        await user.click(toggle);
        expect(toggle).toHaveAttribute("aria-checked", "false");
    });

    test("detail mode toggle can be toggled back on", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);
        const toggle = screen.getByRole("switch");
        await user.click(toggle);
        expect(toggle).toHaveAttribute("aria-checked", "false");
        await user.click(toggle);
        expect(toggle).toHaveAttribute("aria-checked", "true");
    });

    test("re-center button is clickable", async () => {
        const user = userEvent.setup();
        renderPanel([makeStep()]);
        const btn = screen.getByRole("button", { name: /center workflow/i });
        await user.click(btn);
        expect(btn).toBeInTheDocument();
    });

    test("renders with agent name display map without error", () => {
        renderPanel([makeStep()], { "agent-1": "My Agent Display Name" });
        expect(screen.queryByText(/No steps to display/)).not.toBeInTheDocument();
    });

    test("renders multiple steps without error", () => {
        const steps = [makeStep({ id: "step-1", type: "USER_REQUEST", title: "User Input" }), makeStep({ id: "step-2", type: "TASK_COMPLETED", title: "Done" })];
        renderPanel(steps);
        expect(screen.queryByText(/No steps to display/)).not.toBeInTheDocument();
    });

    test("empty state does not render controls bar", () => {
        renderPanel([]);
        expect(screen.queryByRole("button", { name: /center workflow/i })).not.toBeInTheDocument();
        expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    });

    test("renders PanZoomCanvas container for the workflow", () => {
        const { container } = renderPanel([makeStep()]);
        const canvasDiv = container.querySelector("[style*='overflow: hidden']");
        expect(canvasDiv).toBeInTheDocument();
    });

    test("renders workflow node cards inside canvas", () => {
        const { container } = renderPanel([makeStep()]);
        const nodeCards = container.querySelectorAll("[class*='card-surface']");
        expect(nodeCards.length).toBeGreaterThan(0);
    });
});
