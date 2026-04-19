/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

import { TaskCard } from "@/lib/components/scheduled-tasks/TaskCard";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

expect.extend(matchers);

// Mock formatSchedule so we control the displayed schedule text
vi.mock("@/lib/components/scheduled-tasks/utils", () => ({
    formatSchedule: vi.fn(() => "Daily at 09:00"),
}));

function createMockTask(overrides: Partial<ScheduledTask> = {}): ScheduledTask {
    return {
        id: "task-1",
        name: "Daily Report",
        description: "Generate a daily summary report",
        namespace: "default",
        createdBy: "user-1",
        scheduleType: "cron",
        scheduleExpression: "0 9 * * *",
        timezone: "UTC",
        targetAgentName: "report-agent",
        targetType: "agent",
        taskMessage: [{ type: "text", text: "Generate report" }],
        enabled: true,
        status: "active",
        maxRetries: 3,
        retryDelaySeconds: 60,
        timeoutSeconds: 300,
        consecutiveFailureCount: 0,
        runCount: 10,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        nextRunAt: Date.now() + 3600000,
        ...overrides,
    };
}

const defaultProps = {
    onTaskClick: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onToggleEnabled: vi.fn(),
    onViewExecutions: vi.fn(),
};

function renderTaskCard(taskOverrides: Partial<ScheduledTask> = {}, props: Partial<React.ComponentProps<typeof TaskCard>> = {}) {
    const task = createMockTask(taskOverrides);
    return render(<TaskCard task={task} {...defaultProps} {...props} />);
}

describe("TaskCard", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders task name and description", () => {
        renderTaskCard();
        expect(screen.getByText("Daily Report")).toBeInTheDocument();
        expect(screen.getByText("Generate a daily summary report")).toBeInTheDocument();
    });

    it("shows correct status indicator - active (green dot)", () => {
        renderTaskCard({ status: "active" });
        const label = screen.getByText("Active");
        expect(label).toBeInTheDocument();
        const dot = label.previousElementSibling as HTMLElement | null;
        expect(dot?.className).toContain("success");
    });

    it("shows correct status indicator - paused (warning dot)", () => {
        renderTaskCard({ status: "paused" });
        const labels = screen.getAllByText("Paused");
        const label = labels.find(el => el.className.includes("font-medium"));
        expect(label).toBeInTheDocument();
        const dot = label!.previousElementSibling as HTMLElement | null;
        expect(dot?.className).toContain("warning");
    });

    it("shows correct status indicator - error (red dot)", () => {
        renderTaskCard({ status: "error" });
        const label = screen.getByText("Error");
        expect(label).toBeInTheDocument();
        const dot = label.previousElementSibling as HTMLElement | null;
        expect(dot?.className).toContain("error");
    });

    it("shows schedule description from formatSchedule", () => {
        renderTaskCard();
        expect(screen.getByText("Daily at 09:00")).toBeInTheDocument();
    });

    it("shows 'Config' badge when source is 'config'", () => {
        renderTaskCard({ source: "config" });
        expect(screen.getByText("Config")).toBeInTheDocument();
    });

    it("does not show 'Config' badge when source is not 'config'", () => {
        renderTaskCard({ source: "api" });
        expect(screen.queryByText("Config")).not.toBeInTheDocument();
    });

    it("calls onTaskClick when card is clicked", () => {
        const onTaskClick = vi.fn();
        renderTaskCard({}, { onTaskClick });
        // Click on the task name area (inside the card)
        fireEvent.click(screen.getByText("Daily Report"));
        expect(onTaskClick).toHaveBeenCalled();
    });

    it("dropdown menu shows actions when trigger is clicked", () => {
        renderTaskCard();
        // Open the dropdown menu
        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);

        expect(screen.getByText("Edit Task")).toBeInTheDocument();
        expect(screen.getByText("View Execution History")).toBeInTheDocument();
        expect(screen.getByText("Pause Task")).toBeInTheDocument();
        expect(screen.getByText("Delete Task")).toBeInTheDocument();
    });

    it("shows 'Enable Task' when task is disabled", () => {
        renderTaskCard({ enabled: false });
        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);

        expect(screen.getByText("Enable Task")).toBeInTheDocument();
    });

    it("calls onToggleEnabled with correct task when Enable/Disable is clicked", () => {
        const onToggleEnabled = vi.fn();
        const task = createMockTask({ enabled: true });
        render(<TaskCard task={task} {...defaultProps} onToggleEnabled={onToggleEnabled} />);

        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);
        fireEvent.click(screen.getByText("Pause Task"));

        expect(onToggleEnabled).toHaveBeenCalledWith(task);
    });

    it("calls onDelete with task id when delete is clicked", () => {
        const onDelete = vi.fn();
        const task = createMockTask({ id: "task-42" });
        render(<TaskCard task={task} {...defaultProps} onDelete={onDelete} />);

        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);
        fireEvent.click(screen.getByText("Delete Task"));

        expect(onDelete).toHaveBeenCalledWith("task-42");
    });

    it("calls onEdit with task when edit is clicked", () => {
        const onEdit = vi.fn();
        const task = createMockTask();
        render(<TaskCard task={task} {...defaultProps} onEdit={onEdit} />);

        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);
        fireEvent.click(screen.getByText("Edit Task"));

        expect(onEdit).toHaveBeenCalledWith(task);
    });

    it("calls onViewExecutions when View Execution History is clicked", () => {
        const onViewExecutions = vi.fn();
        const task = createMockTask();
        render(<TaskCard task={task} {...defaultProps} onViewExecutions={onViewExecutions} />);

        const menuTrigger = screen.getByRole("button", { name: /actions/i });
        fireEvent.click(menuTrigger);
        fireEvent.click(screen.getByText("View Execution History"));

        expect(onViewExecutions).toHaveBeenCalledWith(task);
    });

    it("shows selected state via aria-selected attribute", () => {
        renderTaskCard({}, { isSelected: true });
        const selectedCard = document.querySelector("[aria-selected='true']");
        expect(selectedCard).toBeInTheDocument();
    });

    it("does not show selected state when isSelected is false", () => {
        renderTaskCard({}, { isSelected: false });
        const selectedCard = document.querySelector("[aria-selected='true']");
        expect(selectedCard).not.toBeInTheDocument();
    });

    describe("Run Now menu item", () => {
        it("shows 'Run Now' when onRunNow is provided for a cron task", () => {
            renderTaskCard({ scheduleType: "cron" }, { onRunNow: vi.fn() });
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            expect(screen.getByText("Run Now")).toBeInTheDocument();
        });

        it("shows 'Run Now' for interval tasks", () => {
            renderTaskCard({ scheduleType: "interval", scheduleExpression: "30m" }, { onRunNow: vi.fn() });
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            expect(screen.getByText("Run Now")).toBeInTheDocument();
        });

        it("hides 'Run Now' for one_time tasks (they are terminal)", () => {
            renderTaskCard({ scheduleType: "one_time", scheduleExpression: "2030-01-01T00:00:00Z" }, { onRunNow: vi.fn() });
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            expect(screen.queryByText("Run Now")).not.toBeInTheDocument();
        });

        it("hides 'Run Now' for config-sourced tasks (read-only)", () => {
            renderTaskCard({ source: "config" }, { onRunNow: vi.fn() });
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            expect(screen.queryByText("Run Now")).not.toBeInTheDocument();
        });

        it("hides 'Run Now' entirely when onRunNow is not provided", () => {
            renderTaskCard();
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            expect(screen.queryByText("Run Now")).not.toBeInTheDocument();
        });

        it("calls onRunNow with the task when the menu item is selected", () => {
            const onRunNow = vi.fn();
            const task = createMockTask();
            render(<TaskCard task={task} {...defaultProps} onRunNow={onRunNow} />);

            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            fireEvent.click(screen.getByText("Run Now"));

            expect(onRunNow).toHaveBeenCalledWith(task);
        });

        it("renders as disabled and shows 'Running…' when isRunNowPending is true", () => {
            const onRunNow = vi.fn();
            renderTaskCard({}, { onRunNow, isRunNowPending: true });
            const menuTrigger = screen.getByRole("button", { name: /actions/i });
            fireEvent.click(menuTrigger);
            const item = screen.getByText("Running…").closest("[role='menuitem']");
            expect(item).toBeInTheDocument();
            expect(item).toHaveAttribute("data-disabled");
        });
    });
});
