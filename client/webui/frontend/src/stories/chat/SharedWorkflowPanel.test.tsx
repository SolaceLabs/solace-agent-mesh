/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";
import type { SharedTaskEvents } from "@/lib/types/share";
import type { VisualizerStep } from "@/lib/types";

expect.extend(matchers);

const mockProcessTask = vi.fn();

describe("SharedWorkflowPanel", () => {
    let SharedWorkflowPanel: React.ComponentType<{
        taskEvents: Record<string, SharedTaskEvents> | null | undefined;
        selectedTaskId: string | null;
        onTaskSelect: (taskId: string) => void;
    }>;

    beforeEach(async () => {
        vi.resetModules();
        mockProcessTask.mockReset();

        vi.doMock("@/lib/components/activities/taskVisualizerProcessor", () => ({
            processTaskForVisualization: mockProcessTask,
        }));

        vi.doMock("@/lib/components/share/SharedFlowChartPanel", () => ({
            SharedFlowChartPanel: ({ processedSteps }: { processedSteps: VisualizerStep[] }) => React.createElement("div", { "data-testid": "flow-chart-panel" }, `Steps: ${processedSteps.length}`),
        }));

        const mod = await import("@/lib/components/share/SharedWorkflowPanel");
        SharedWorkflowPanel = mod.SharedWorkflowPanel;
    });

    function makeTaskEvents(overrides: Partial<SharedTaskEvents> = {}): SharedTaskEvents {
        return {
            taskId: "task-1",
            events: [
                {
                    eventType: "request",
                    timestamp: "2025-01-15T10:00:00Z",
                    solaceTopic: "topic/request",
                    direction: "request",
                    sourceEntity: "User",
                    targetEntity: "Agent",
                    messageId: "msg-1",
                    taskId: "task-1",
                    payloadSummary: { method: "ask", paramsPreview: "hello" },
                    fullPayload: {},
                },
            ],
            initialRequestText: "Hello agent",
            ...overrides,
        };
    }

    function makeVisualizerStep(overrides: Partial<VisualizerStep> = {}): VisualizerStep {
        return {
            id: "step-1",
            type: "USER_REQUEST",
            timestamp: "2025-01-15T10:00:00Z",
            title: "User Request",
            data: {},
            rawEventIds: ["evt-1"],
            nestingLevel: 0,
            owningTaskId: "task-1",
            ...overrides,
        };
    }

    test("shows 'No workflow data' when taskEvents is null", () => {
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents: null,
                selectedTaskId: null,
                onTaskSelect: vi.fn(),
            })
        );
        expect(screen.getByText("No workflow data available for this session")).toBeInTheDocument();
    });

    test("shows 'No workflow data' when taskEvents is empty object", () => {
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents: {},
                selectedTaskId: null,
                onTaskSelect: vi.fn(),
            })
        );
        expect(screen.getByText("No workflow data available for this session")).toBeInTheDocument();
    });

    test("shows 'Unable to process' when processTaskForVisualization returns null", () => {
        mockProcessTask.mockReturnValue(null);

        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: "task-1",
                onTaskSelect: vi.fn(),
            })
        );
        expect(screen.getByText("Unable to process workflow data")).toBeInTheDocument();
    });

    test("renders flow chart panel when visualization succeeds", () => {
        const steps = [makeVisualizerStep(), makeVisualizerStep({ id: "step-2", title: "Step 2" })];
        mockProcessTask.mockReturnValue({
            taskId: "task-1",
            initialRequestText: "Hello agent",
            status: "completed",
            startTime: "2025-01-15T10:00:00Z",
            steps,
        });

        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: "task-1",
                onTaskSelect: vi.fn(),
            })
        );

        expect(screen.getByTestId("flow-chart-panel")).toBeInTheDocument();
        expect(screen.getByText("Steps: 2")).toBeInTheDocument();
    });

    test("displays the initial request text in flow chart details", () => {
        mockProcessTask.mockReturnValue({
            taskId: "task-1",
            initialRequestText: "Hello agent",
            status: "completed",
            startTime: "2025-01-15T10:00:00Z",
            steps: [makeVisualizerStep()],
        });

        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: "task-1",
                onTaskSelect: vi.fn(),
            })
        );

        expect(screen.getByText("Hello agent")).toBeInTheDocument();
    });

    test("displays status badge for completed task", () => {
        mockProcessTask.mockReturnValue({
            taskId: "task-1",
            initialRequestText: "Hello",
            status: "completed",
            startTime: "2025-01-15T10:00:00Z",
            steps: [makeVisualizerStep()],
        });

        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: "task-1",
                onTaskSelect: vi.fn(),
            })
        );

        expect(screen.getByText("Completed")).toBeInTheDocument();
    });

    test("auto-selects root task when no task is selected", () => {
        mockProcessTask.mockReturnValue(null);

        const onTaskSelect = vi.fn();
        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: null,
                onTaskSelect,
            })
        );

        expect(onTaskSelect).toHaveBeenCalledWith("task-1");
    });

    test("shows 'No request text' when initialRequestText is empty", () => {
        mockProcessTask.mockReturnValue({
            taskId: "task-1",
            initialRequestText: "",
            status: "working",
            startTime: "2025-01-15T10:00:00Z",
            steps: [makeVisualizerStep()],
        });

        const taskEvents = { "task-1": makeTaskEvents() };
        render(
            React.createElement(SharedWorkflowPanel, {
                taskEvents,
                selectedTaskId: "task-1",
                onTaskSelect: vi.fn(),
            })
        );

        expect(screen.getByText("No request text")).toBeInTheDocument();
    });
});
