// Pure cron <-> ScheduleConfig conversion and validation.
// Extracted from ScheduleBuilder so it's unit-testable without rendering
// the Radix-driven UI.

export const DAY_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export type FrequencyType = "daily" | "weekly" | "monthly" | "custom";

// Nth occurrence within a month: "1"=First, "2"=Second, "3"=Third, "4"=Fourth, "L"=Last.
export type MonthNth = "1" | "2" | "3" | "4" | "L";

// "weekday" → Nth weekday of the month (e.g. "First Monday"); "date" → numeric
// day-of-month (e.g. "the 15th"). Legacy tasks created before the Nth-weekday
// builder used the date form, so we still need to parse and emit it.
export type MonthlyMode = "weekday" | "date";

export const MONTH_NTH_LABELS: Record<MonthNth, string> = {
    "1": "First",
    "2": "Second",
    "3": "Third",
    "4": "Fourth",
    L: "Last",
};

export interface ScheduleConfig {
    frequency: FrequencyType;
    time: string; // HH:MM format (12-hour, paired with `ampm`)
    ampm: "AM" | "PM";
    weekDays: number[]; // 0-6 (Sunday-Saturday)
    monthlyMode: MonthlyMode;
    monthNth: MonthNth; // which occurrence of the chosen weekday in the month
    monthWeekday: number; // 0-6 (Sunday-Saturday)
    monthDay: number; // 1-31, used when monthlyMode === "date"
}

// Convert schedule config to cron expression.
export function scheduleToCron(config: ScheduleConfig): string {
    const parts = config.time.split(":");
    const hours12 = Number(parts[0]);
    const minutes = Number(parts[1]);

    // Guard against partial/invalid time input producing NaN in cron.
    if (isNaN(hours12) || isNaN(minutes)) {
        return "0 9 * * *"; // Safe default
    }

    let hour = hours12;

    // Convert 12-hour to 24-hour format
    if (config.ampm === "PM") {
        hour = hours12 === 12 ? 12 : hours12 + 12;
    } else if (config.ampm === "AM") {
        hour = hours12 === 12 ? 0 : hours12;
    }

    switch (config.frequency) {
        case "daily":
            return `${minutes} ${hour} * * *`;

        case "weekly": {
            if (config.weekDays.length === 0) return `${minutes} ${hour} * * *`;
            const days = [...config.weekDays].sort((a, b) => a - b).join(",");
            return `${minutes} ${hour} * * ${days}`;
        }

        case "monthly": {
            if (config.monthlyMode === "date") {
                const day = Math.max(1, Math.min(31, Math.floor(config.monthDay) || 1));
                return `${minutes} ${hour} ${day} * *`;
            }
            const wd = config.monthWeekday;
            // croniter accepts both `D#N` (Nth weekday) and `DL` (last weekday).
            if (config.monthNth === "L") {
                return `${minutes} ${hour} * * ${wd}L`;
            }
            return `${minutes} ${hour} * * ${wd}#${config.monthNth}`;
        }

        default:
            return `${minutes} ${hour} * * *`;
    }
}

// Normalize a cron expression for equivalence comparison:
// sorts & dedupes comma-separated numeric lists so `3,1` === `1,3`.
export function normalizeCron(cron: string): string {
    return cron
        .trim()
        .split(/\s+/)
        .map(field => {
            if (!field.includes(",")) return field;
            const nums = field.split(",").map(Number);
            if (nums.some(n => isNaN(n))) return field;
            return [...new Set(nums)].sort((a, b) => a - b).join(",");
        })
        .join(" ");
}

// Parse cron expression to schedule config. When the input uses a pattern
// the preset builder can't fully represent (e.g. month != *, ranges, steps
// in unexpected fields), falls back to "custom" so the original expression
// is preserved verbatim instead of being silently rewritten on save.
export function cronToSchedule(cron: string): ScheduleConfig | null {
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5) return null;

    const [minute, hour, dayOfMonth, , dayOfWeek] = parts;

    // Parse time
    let hours24 = 9;
    let minutes = 0;

    if (hour !== "*" && !hour.includes("/")) {
        hours24 = parseInt(hour);
    }
    if (minute !== "*" && !minute.includes("/")) {
        minutes = parseInt(minute);
    }

    // Convert to 12-hour format
    let ampm: "AM" | "PM" = "AM";
    let hours12 = hours24;
    if (hours24 >= 12) {
        ampm = "PM";
        if (hours24 > 12) hours12 = hours24 - 12;
    } else if (hours24 === 0) {
        hours12 = 12;
    }

    const time = `${hours12.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

    const customFallback: ScheduleConfig = {
        frequency: "custom",
        time,
        ampm,
        weekDays: [],
        monthlyMode: "weekday",
        monthNth: "1",
        monthWeekday: 1,
        monthDay: 1,
    };

    let candidate: ScheduleConfig;

    if (minute.includes("/") || hour.includes("/")) {
        // Step patterns (e.g. "*/15 * * * *", "0 */6 * * *") have no preset
        // representation now that Hourly is gone — preserve verbatim as custom.
        return customFallback;
    } else if (dayOfMonth === "*" && /^\d#[1-4]$/.test(dayOfWeek)) {
        // Nth weekday of month, e.g. "1#1" = first Monday.
        const [wdStr, nStr] = dayOfWeek.split("#");
        const wd = parseInt(wdStr);
        if (wd < 0 || wd > 6) return customFallback;
        candidate = { frequency: "monthly", time, ampm, weekDays: [], monthlyMode: "weekday", monthNth: nStr as MonthNth, monthWeekday: wd, monthDay: 1 };
    } else if (dayOfMonth === "*" && /^\dL$/i.test(dayOfWeek)) {
        // Last weekday of month, e.g. "5L" = last Friday.
        const wd = parseInt(dayOfWeek[0]);
        if (wd < 0 || wd > 6) return customFallback;
        candidate = { frequency: "monthly", time, ampm, weekDays: [], monthlyMode: "weekday", monthNth: "L", monthWeekday: wd, monthDay: 1 };
    } else if (dayOfWeek === "*" && /^\d+$/.test(dayOfMonth)) {
        // Numeric day-of-month, e.g. "0 9 15 * *" = the 15th at 9am.
        const day = parseInt(dayOfMonth);
        if (day < 1 || day > 31) return customFallback;
        candidate = { frequency: "monthly", time, ampm, weekDays: [], monthlyMode: "date", monthNth: "1", monthWeekday: 1, monthDay: day };
    } else if (dayOfWeek !== "*" && /^\d+(,\d+)*$/.test(dayOfWeek)) {
        const days = dayOfWeek.split(",").map(d => parseInt(d));
        candidate = { frequency: "weekly", time, ampm, weekDays: days, monthlyMode: "weekday", monthNth: "1", monthWeekday: 1, monthDay: 1 };
    } else if (dayOfMonth === "*" && dayOfWeek === "*") {
        candidate = { frequency: "daily", time, ampm, weekDays: [], monthlyMode: "weekday", monthNth: "1", monthWeekday: 1, monthDay: 1 };
    } else {
        // Anything else (ranges, lists in dayOfMonth, etc.) — preserve verbatim.
        return customFallback;
    }

    // If the preset candidate doesn't roundtrip to the input, the cron has
    // structure we can't represent — keep the original as a custom expression.
    if (normalizeCron(scheduleToCron(candidate)) !== normalizeCron(cron)) {
        return customFallback;
    }
    return candidate;
}

// Helper function to generate human-readable schedule description.
export function getScheduleDescription(config: ScheduleConfig): string {
    const timeStr = `${config.time} ${config.ampm}`;

    switch (config.frequency) {
        case "daily":
            return `Every day at ${timeStr}`;

        case "weekly": {
            if (config.weekDays.length === 0) return `Every day at ${timeStr}`;
            const days = [...config.weekDays]
                .sort((a, b) => a - b)
                .map(d => DAY_LABELS[d])
                .join(", ");
            return `Every ${days} at ${timeStr}`;
        }

        case "monthly": {
            if (config.monthlyMode === "date") {
                const day = Math.max(1, Math.min(31, Math.floor(config.monthDay) || 1));
                const mod100 = day % 100;
                const suffix = mod100 >= 11 && mod100 <= 13 ? "th" : day % 10 === 1 ? "st" : day % 10 === 2 ? "nd" : day % 10 === 3 ? "rd" : "th";
                return `Monthly on the ${day}${suffix} at ${timeStr}`;
            }
            const dayName = DAY_LABELS[config.monthWeekday] || "Monday";
            const ordinal = MONTH_NTH_LABELS[config.monthNth].toLowerCase();
            return `${ordinal === "last" ? "Last" : ordinal[0].toUpperCase() + ordinal.slice(1)} ${dayName} of every month at ${timeStr}`;
        }

        default:
            return "Custom schedule";
    }
}

// Validate a cron field. Supports lists of any element type:
// wildcards, singles, ranges (a-b), and steps (*/n or a-b/n).
function isValidCronField(field: string, min: number, max: number): boolean {
    if (!field) return false;
    if (field.includes(",")) {
        return field.split(",").every(element => isValidCronElement(element, min, max));
    }
    return isValidCronElement(field, min, max);
}

function isValidCronElement(element: string, min: number, max: number): boolean {
    if (!element) return false;

    // Step: <base>/<step>, where base is '*' or a range
    if (element.includes("/")) {
        const [base, stepStr] = element.split("/");
        const step = parseInt(stepStr);
        if (isNaN(step) || String(step) !== stepStr || step <= 0 || step > max) return false;
        if (base === "*") return true;
        if (base.includes("-")) return isValidCronRange(base, min, max);
        return false;
    }

    if (element.includes("-")) return isValidCronRange(element, min, max);
    if (element === "*") return true;

    const value = parseInt(element);
    return !isNaN(value) && String(value) === element && value >= min && value <= max;
}

function isValidCronRange(range: string, min: number, max: number): boolean {
    const parts = range.split("-");
    if (parts.length !== 2) return false;
    const [start, end] = parts.map(Number);
    if (isNaN(start) || isNaN(end)) return false;
    if (String(start) !== parts[0] || String(end) !== parts[1]) return false;
    return start >= min && end <= max && start <= end;
}

// Validate cron expression.
export function validateCron(cron: string): { valid: boolean; error?: string } {
    const trimmed = cron.trim();
    if (!trimmed) {
        return { valid: false, error: "Cron expression cannot be empty" };
    }

    const parts = trimmed.split(/\s+/);
    if (parts.length !== 5) {
        return { valid: false, error: "Cron expression must have exactly 5 fields (minute hour day month weekday)" };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    if (!isValidCronField(minute, 0, 59)) {
        return { valid: false, error: "Invalid minute field (must be 0-59 or * or */n)" };
    }
    if (!isValidCronField(hour, 0, 23)) {
        return { valid: false, error: "Invalid hour field (must be 0-23 or * or */n)" };
    }
    if (!isValidCronField(dayOfMonth, 1, 31)) {
        return { valid: false, error: "Invalid day of month field (must be 1-31 or * or */n)" };
    }
    if (!isValidCronField(month, 1, 12)) {
        return { valid: false, error: "Invalid month field (must be 1-12 or * or */n)" };
    }
    if (!isValidCronField(dayOfWeek, 0, 6)) {
        return { valid: false, error: "Invalid day of week field (must be 0-6 or * or */n)" };
    }

    return { valid: true };
}
