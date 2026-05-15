/// <reference types="@testing-library/jest-dom" />
import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";

import { ScheduleBuilder } from "@/lib/components/scheduled-tasks/ScheduleBuilder";

expect.extend(matchers);

// The Frequency dropdown in this builder is a Radix Select (not a native
// <select>), so we can't drive it with fireEvent.change. The component does
// reflect the `value` prop into the visible state, so most behaviors are
// reachable by varying `value` instead of clicking through Radix. The cron
// input in custom mode is a real <input> and can be typed into directly.

function renderBuilder(props: Partial<React.ComponentProps<typeof ScheduleBuilder>> = {}) {
    const defaultProps = {
        value: "0 9 * * *",
        onChange: vi.fn(),
        ...props,
    };
    return { ...render(<ScheduleBuilder {...defaultProps} />), onChange: defaultProps.onChange };
}

describe("ScheduleBuilder", () => {
    it("calls onChange on initial mount with the canonical cron", () => {
        const onChange = vi.fn();
        renderBuilder({ value: "0 9 * * *", onChange });
        expect(onChange).toHaveBeenCalledWith("0 9 * * *");
    });

    it("falls back to custom mode for non-representable cron and preserves the original", () => {
        // "0 0 1 1 *" = Jan 1 at midnight. Month != * so the simple-mode
        // presets can't represent it; the builder should expose the raw
        // expression in the custom cron input.
        renderBuilder({ value: "0 0 1 1 *" });

        const cronInput = screen.getByPlaceholderText("0 9 * * *");
        expect(cronInput).toHaveValue("0 0 1 1 *");
    });

    it("custom mode validates cron — invalid cron shows error", () => {
        // Enter custom mode by passing a non-representable value.
        renderBuilder({ value: "0 0 1 1 *" });

        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        // Too few fields
        fireEvent.change(cronInput, { target: { value: "* *" } });
        expect(screen.getByText(/Cron expression must have exactly 5 fields/)).toBeInTheDocument();

        // Valid → error clears
        fireEvent.change(cronInput, { target: { value: "0 9 * * 1" } });
        expect(screen.queryByText(/Cron expression must have exactly 5 fields/)).not.toBeInTheDocument();
    });

    it("custom mode rejects out-of-range cron values", () => {
        renderBuilder({ value: "0 0 1 1 *" });
        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        fireEvent.change(cronInput, { target: { value: "0 25 * * *" } });
        expect(screen.getByText(/Invalid hour field/)).toBeInTheDocument();
    });

    it("custom mode accepts complex cron grammar (ranges, steps, lists)", () => {
        renderBuilder({ value: "0 0 1 1 *" });
        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        // range with step: every 2 hours between 9-17
        fireEvent.change(cronInput, { target: { value: "0 9-17/2 * * 1-5" } });
        expect(screen.queryByText(/Invalid/)).not.toBeInTheDocument();

        // list of ranges + singles on the weekday field
        fireEvent.change(cronInput, { target: { value: "0 9 * * 1-3,5" } });
        expect(screen.queryByText(/Invalid/)).not.toBeInTheDocument();

        // mixed list: step + single on the minute field
        fireEvent.change(cronInput, { target: { value: "*/15,30 * * * *" } });
        expect(screen.queryByText(/Invalid/)).not.toBeInTheDocument();
    });

    it("custom mode shows the friendly preview for a valid cron", () => {
        renderBuilder({ value: "0 0 1 1 *" });
        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        // Override with a cron the description function can translate.
        // Use 2:00 PM Mondays so the description doesn't collide with the
        // example list (which includes "Every Monday at 9:00 AM").
        fireEvent.change(cronInput, { target: { value: "0 14 * * 1" } });

        expect(screen.getByText(/Every Monday at 2:00 PM/)).toBeInTheDocument();
    });

    it("emits cron updates through onChange when the cron input changes", () => {
        const onChange = vi.fn();
        renderBuilder({ value: "0 0 1 1 *", onChange });
        const cronInput = screen.getByPlaceholderText("0 9 * * *");

        onChange.mockClear();
        fireEvent.change(cronInput, { target: { value: "0 14 * * 1" } });

        expect(onChange).toHaveBeenCalledWith("0 14 * * 1");
    });
});
