import { describe, it, expect } from "vitest";
import { formatSchedule, describeScheduleExpression } from "@/lib/components/scheduled-tasks/utils";
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

describe("describeScheduleExpression", () => {
    it("translates a daily cron into 12-hour plain English", () => {
        expect(describeScheduleExpression("cron", "40 15 * * *")).toBe("Every day at 3:40 PM");
        expect(describeScheduleExpression("cron", "0 9 * * *")).toBe("Every day at 9:00 AM");
        expect(describeScheduleExpression("cron", "0 0 * * *")).toBe("Every day at 12:00 AM");
        expect(describeScheduleExpression("cron", "0 12 * * *")).toBe("Every day at 12:00 PM");
    });

    it("translates weekly cron patterns", () => {
        expect(describeScheduleExpression("cron", "0 9 * * 1")).toBe("Every Monday at 9:00 AM");
        expect(describeScheduleExpression("cron", "0 9 * * 1,2,3,4,5")).toBe("Weekdays at 9:00 AM");
        expect(describeScheduleExpression("cron", "0 9 * * 0,6")).toBe("Weekends at 9:00 AM");
        expect(describeScheduleExpression("cron", "0 9 * * 1,3,5")).toBe("Mon, Wed, Fri at 9:00 AM");
    });

    it("translates monthly cron with ordinal day", () => {
        expect(describeScheduleExpression("cron", "0 0 1 * *")).toBe("Monthly on the 1st at 12:00 AM");
        expect(describeScheduleExpression("cron", "30 13 22 * *")).toBe("Monthly on the 22nd at 1:30 PM");
    });

    it("translates step-based cron patterns", () => {
        expect(describeScheduleExpression("cron", "0 */6 * * *")).toBe("Every 6 hours");
        expect(describeScheduleExpression("cron", "*/15 * * * *")).toBe("Every 15 minutes");
        expect(describeScheduleExpression("cron", "30 */6 * * *")).toBe("Every 6 hours at :30");
    });

    it("falls back to the raw expression when it can't be translated", () => {
        // month field restricted — not representable by our presets
        expect(describeScheduleExpression("cron", "0 0 1 1 *")).toBe("0 0 1 1 *");
        expect(describeScheduleExpression("cron", "not a cron")).toBe("not a cron");
    });

    it("describes intervals in plain English", () => {
        expect(describeScheduleExpression("interval", "30m")).toBe("Every 30 minutes");
        expect(describeScheduleExpression("interval", "1h")).toBe("Every hour");
        expect(describeScheduleExpression("interval", "2h")).toBe("Every 2 hours");
        expect(describeScheduleExpression("interval", "1d")).toBe("Every day");
    });

    it("describes one-time dates in localized long form", () => {
        const result = describeScheduleExpression("one_time", "2026-06-15T14:30:00.000Z");
        expect(result).toContain("Jun");
        expect(result).toContain("15");
        expect(result).toContain("2026");
    });

    it("returns 'Not set' for empty expressions", () => {
        expect(describeScheduleExpression("cron", "")).toBe("Not set");
    });
});
