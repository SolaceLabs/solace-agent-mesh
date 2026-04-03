import { describe, it, expect } from "vitest";
import { formatSchedule } from "@/lib/components/scheduled-tasks/utils";
import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

describe("formatSchedule", () => {
    describe("cron patterns", () => {
        it("formats daily cron pattern", () => {
            const task = { scheduleType: "cron", scheduleExpression: "0 9 * * *" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Daily at 09:00");
        });

        it("formats weekly cron pattern", () => {
            const task = { scheduleType: "cron", scheduleExpression: "0 14 * * 1,3,5" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Mon, Wed, Fri at 14:00");
        });

        it("formats monthly cron pattern", () => {
            const task = { scheduleType: "cron", scheduleExpression: "0 9 15 * *" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Monthly on day 15 at 09:00");
        });

        it("formats hourly cron pattern", () => {
            const task = { scheduleType: "cron", scheduleExpression: "0 */6 * * *" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Every 6 hours");
        });

        it("falls back to raw cron for unparseable 5-part expression", () => {
            const task = { scheduleType: "cron", scheduleExpression: "* * * * *" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Cron: * * * * *");
        });

        it("returns raw cron for non-5-part expression", () => {
            const task = { scheduleType: "cron", scheduleExpression: "0 0 1 1 * 2026" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Cron: 0 0 1 1 * 2026");
        });
    });

    describe("interval", () => {
        it("formats interval schedule", () => {
            const task = { scheduleType: "interval", scheduleExpression: "30m" } as ScheduledTask;
            expect(formatSchedule(task)).toBe("Every 30m");
        });
    });

    describe("one-time", () => {
        it("formats one-time ISO date string", () => {
            const task = {
                scheduleType: "one_time",
                scheduleExpression: "2026-06-15T14:30:00.000Z",
            } as ScheduledTask;
            const result = formatSchedule(task);
            expect(result).toMatch(/^One time: /);
            // The formatted date should contain recognizable parts of the date
            expect(result).toContain("Jun");
            expect(result).toContain("15");
            expect(result).toContain("2026");
        });
    });
});
