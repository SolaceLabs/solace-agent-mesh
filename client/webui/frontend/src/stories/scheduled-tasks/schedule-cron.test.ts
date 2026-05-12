import { describe, it, expect } from "vitest";

import { cronToSchedule, getScheduleDescription, scheduleToCron, validateCron, type ScheduleConfig } from "@/lib/components/scheduled-tasks/schedule-cron";

const baseConfig: ScheduleConfig = {
    frequency: "daily",
    time: "09:00",
    ampm: "AM",
    weekDays: [],
    monthlyMode: "weekday",
    monthNth: "1",
    monthWeekday: 1,
    monthDay: 1,
};

describe("scheduleToCron", () => {
    it("emits daily cron at the configured 24-hour time", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "daily", time: "09:00", ampm: "AM" })).toBe("0 9 * * *");
        expect(scheduleToCron({ ...baseConfig, frequency: "daily", time: "02:30", ampm: "PM" })).toBe("30 14 * * *");
    });

    it("12 AM maps to hour 0, 12 PM maps to hour 12 (handles AM/PM noon/midnight edge cases)", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "daily", time: "12:00", ampm: "AM" })).toBe("0 0 * * *");
        expect(scheduleToCron({ ...baseConfig, frequency: "daily", time: "12:00", ampm: "PM" })).toBe("0 12 * * *");
    });

    it("weekly emits a sorted day-of-week list regardless of selection order", () => {
        // Days 3,1,5 should canonicalize to 1,3,5 — order independence matters
        // because cron parsers compare on equality.
        expect(scheduleToCron({ ...baseConfig, frequency: "weekly", weekDays: [3, 1, 5] })).toBe("0 9 * * 1,3,5");
    });

    it("weekly with empty selection falls back to daily cron (no day filter)", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "weekly", weekDays: [] })).toBe("0 9 * * *");
    });

    it("monthly weekday emits D#N for ordinals and DL for last", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "monthly", monthlyMode: "weekday", monthNth: "1", monthWeekday: 1 })).toBe("0 9 * * 1#1");
        expect(scheduleToCron({ ...baseConfig, frequency: "monthly", monthlyMode: "weekday", monthNth: "L", monthWeekday: 5 })).toBe("0 9 * * 5L");
    });

    it("monthly date emits the numeric day-of-month and clamps invalid values", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "monthly", monthlyMode: "date", monthDay: 15 })).toBe("0 9 15 * *");
        // 0 and 99 are out of range — clamp to 1 and 31.
        expect(scheduleToCron({ ...baseConfig, frequency: "monthly", monthlyMode: "date", monthDay: 0 })).toBe("0 9 1 * *");
        expect(scheduleToCron({ ...baseConfig, frequency: "monthly", monthlyMode: "date", monthDay: 99 })).toBe("0 9 31 * *");
    });

    it("falls back to safe daily cron when time is unparseable", () => {
        expect(scheduleToCron({ ...baseConfig, frequency: "daily", time: "ab:cd" })).toBe("0 9 * * *");
    });
});

describe("cronToSchedule", () => {
    it("recognises daily presets", () => {
        const parsed = cronToSchedule("0 9 * * *");
        expect(parsed?.frequency).toBe("daily");
        expect(parsed?.time).toBe("09:00");
        expect(parsed?.ampm).toBe("AM");
    });

    it("recognises weekly preset with multiple days", () => {
        const parsed = cronToSchedule("0 9 * * 1,3,5");
        expect(parsed?.frequency).toBe("weekly");
        expect(parsed?.weekDays).toEqual([1, 3, 5]);
    });

    it("recognises monthly-weekday (D#N) and monthly-last (DL)", () => {
        const nth = cronToSchedule("0 9 * * 1#1");
        expect(nth?.frequency).toBe("monthly");
        expect(nth?.monthlyMode).toBe("weekday");
        expect(nth?.monthNth).toBe("1");
        expect(nth?.monthWeekday).toBe(1);

        const last = cronToSchedule("0 9 * * 5L");
        expect(last?.frequency).toBe("monthly");
        expect(last?.monthNth).toBe("L");
        expect(last?.monthWeekday).toBe(5);
    });

    it("recognises legacy numeric monthly preset (day-of-month)", () => {
        const parsed = cronToSchedule("0 9 15 * *");
        expect(parsed?.frequency).toBe("monthly");
        expect(parsed?.monthlyMode).toBe("date");
        expect(parsed?.monthDay).toBe(15);
    });

    it("falls back to custom for step expressions", () => {
        expect(cronToSchedule("*/15 * * * *")?.frequency).toBe("custom");
        expect(cronToSchedule("0 */6 * * *")?.frequency).toBe("custom");
    });

    it("falls back to custom for non-representable patterns (month != *)", () => {
        expect(cronToSchedule("0 0 1 1 *")?.frequency).toBe("custom");
    });

    it("returns null for malformed inputs (wrong field count)", () => {
        expect(cronToSchedule("* *")).toBeNull();
        expect(cronToSchedule("* * * * * *")).toBeNull();
    });

    it("roundtrips: scheduleToCron(cronToSchedule(x)) preserves preset cron", () => {
        const inputs = ["0 9 * * *", "30 14 * * 1,3,5", "0 9 * * 1#1", "0 9 15 * *", "0 9 * * 5L"];
        for (const cron of inputs) {
            const parsed = cronToSchedule(cron);
            expect(parsed).not.toBeNull();
            if (parsed && parsed.frequency !== "custom") {
                expect(scheduleToCron(parsed)).toBe(cron);
            }
        }
    });
});

describe("validateCron", () => {
    it("accepts canonical 5-field expressions", () => {
        expect(validateCron("0 9 * * *").valid).toBe(true);
        expect(validateCron("*/15 * * * *").valid).toBe(true);
        expect(validateCron("0 9-17/2 * * 1-5").valid).toBe(true);
        expect(validateCron("*/15,30 * * * *").valid).toBe(true);
    });

    it("rejects empty/wrong-length expressions", () => {
        expect(validateCron("").valid).toBe(false);
        expect(validateCron("0 9 * *").valid).toBe(false);
        expect(validateCron("0 9 * * * *").valid).toBe(false);
    });

    it("rejects out-of-range numeric fields", () => {
        expect(validateCron("60 9 * * *").valid).toBe(false); // minute > 59
        expect(validateCron("0 24 * * *").valid).toBe(false); // hour > 23
        expect(validateCron("0 9 32 * *").valid).toBe(false); // day > 31
        expect(validateCron("0 9 * 13 *").valid).toBe(false); // month > 12
        expect(validateCron("0 9 * * 7").valid).toBe(false); // day of week > 6
    });

    it("rejects malformed step/range syntax", () => {
        expect(validateCron("0 */0 * * *").valid).toBe(false);
        expect(validateCron("0 5-3 * * *").valid).toBe(false);
    });
});

describe("getScheduleDescription", () => {
    it("describes daily, weekly, and monthly variants", () => {
        expect(getScheduleDescription({ ...baseConfig, frequency: "daily", time: "09:00", ampm: "AM" })).toBe("Every day at 09:00 AM");
        expect(getScheduleDescription({ ...baseConfig, frequency: "weekly", weekDays: [1, 3, 5] })).toBe("Every Monday, Wednesday, Friday at 09:00 AM");
        expect(getScheduleDescription({ ...baseConfig, frequency: "monthly", monthlyMode: "weekday", monthNth: "1", monthWeekday: 1 })).toBe("First Monday of every month at 09:00 AM");
        expect(getScheduleDescription({ ...baseConfig, frequency: "monthly", monthlyMode: "weekday", monthNth: "L", monthWeekday: 5 })).toBe("Last Friday of every month at 09:00 AM");
        expect(getScheduleDescription({ ...baseConfig, frequency: "monthly", monthlyMode: "date", monthDay: 1 })).toBe("Monthly on the 1st at 09:00 AM");
        expect(getScheduleDescription({ ...baseConfig, frequency: "monthly", monthlyMode: "date", monthDay: 22 })).toBe("Monthly on the 22nd at 09:00 AM");
    });
});
