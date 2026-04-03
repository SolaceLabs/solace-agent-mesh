/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ScheduleBuilder } from "@/lib/components/scheduled-tasks/ScheduleBuilder";

expect.extend(matchers);

function renderBuilder(props: Partial<React.ComponentProps<typeof ScheduleBuilder>> = {}) {
    const defaultProps = {
        value: "0 9 * * *",
        onChange: vi.fn(),
        ...props,
    };
    return { ...render(<ScheduleBuilder {...defaultProps} />), onChange: defaultProps.onChange };
}

describe("ScheduleBuilder", () => {
    it("renders with default daily schedule", () => {
        renderBuilder();

        // Frequency dropdown present with "Daily" selected
        const select = screen.getAllByRole("combobox")[0];
        expect(select).toBeInTheDocument();
        expect(select).toHaveValue("daily");

        // Time input present
        const timeInput = screen.getByPlaceholderText("09:00");
        expect(timeInput).toBeInTheDocument();

        // Preview section present
        expect(screen.getByText("Preview:")).toBeInTheDocument();
    });

    it("preview shows correct text for daily schedule", () => {
        renderBuilder({ value: "0 9 * * *" });

        expect(screen.getByText("Every day at 09:00 AM")).toBeInTheDocument();
    });

    it("changing frequency to weekly shows day selector", () => {
        renderBuilder();

        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "weekly" } });

        // Day buttons should appear
        expect(screen.getByText("Sun")).toBeInTheDocument();
        expect(screen.getByText("Mon")).toBeInTheDocument();
        expect(screen.getByText("Tue")).toBeInTheDocument();
        expect(screen.getByText("Wed")).toBeInTheDocument();
        expect(screen.getByText("Thu")).toBeInTheDocument();
        expect(screen.getByText("Fri")).toBeInTheDocument();
        expect(screen.getByText("Sat")).toBeInTheDocument();
    });

    it("changing frequency to monthly shows day of month selector", () => {
        renderBuilder();

        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "monthly" } });

        // Day of month label should appear
        expect(screen.getByText("Day of Month")).toBeInTheDocument();

        // Day of month dropdown should have values 1-31
        const daySelect = screen.getAllByRole("combobox").find(el => {
            const options = el.querySelectorAll("option");
            return options.length === 31;
        });
        expect(daySelect).toBeInTheDocument();
    });

    it("changing frequency to hourly shows interval selector", () => {
        renderBuilder();

        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "hourly" } });

        // Interval options should appear
        expect(screen.getByText("1 hour")).toBeInTheDocument();
        expect(screen.getByText("2 hours")).toBeInTheDocument();
        expect(screen.getByText("6 hours")).toBeInTheDocument();
        expect(screen.getByText("12 hours")).toBeInTheDocument();
        expect(screen.getByText("24 hours")).toBeInTheDocument();
    });

    it("changing frequency to custom shows cron input", () => {
        renderBuilder();

        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "custom" } });

        // Cron text input should appear
        expect(screen.getByText("Cron Expression")).toBeInTheDocument();
        const cronInput = screen.getByPlaceholderText("0 9 * * *");
        expect(cronInput).toBeInTheDocument();
    });

    it("custom mode validates cron - invalid cron shows error, valid shows checkmark", () => {
        renderBuilder();

        // Switch to custom mode
        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "custom" } });

        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        // Enter invalid cron (too few fields)
        fireEvent.change(cronInput, { target: { value: "* *" } });
        expect(screen.getByText(/Cron expression must have exactly 5 fields/)).toBeInTheDocument();

        // Enter valid cron
        fireEvent.change(cronInput, { target: { value: "0 9 * * 1" } });
        // Error should be gone
        expect(screen.queryByText(/Cron expression must have exactly 5 fields/)).not.toBeInTheDocument();

        // Checkmark (CheckCircle2) should be present - it renders as an svg
        const svgIcon = document.querySelector("svg");
        expect(svgIcon).toBeInTheDocument();
    });

    it("calls onChange with generated cron when config changes", () => {
        const onChange = vi.fn();
        renderBuilder({ onChange });

        // onChange is called on initial render via useEffect
        expect(onChange).toHaveBeenCalledWith("0 9 * * *");

        // Change frequency to weekly and select Monday (index 1)
        const frequencySelect = screen.getAllByRole("combobox")[0];
        fireEvent.change(frequencySelect, { target: { value: "weekly" } });

        // Click Monday button
        fireEvent.click(screen.getByText("Mon"));

        // Should be called with a weekly cron targeting Monday (day 1)
        expect(onChange).toHaveBeenCalledWith("0 9 * * 1");
    });
});
