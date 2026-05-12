import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

const DAY_NAMES_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAY_NAMES_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const formatTime12h = (hour24: number, minute: number): string => {
    const ampm = hour24 >= 12 ? "PM" : "AM";
    const h = hour24 % 12 || 12;
    return `${h}:${String(minute).padStart(2, "0")} ${ampm}`;
};

const ordinal = (n: number): string => {
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
    switch (n % 10) {
        case 1:
            return `${n}st`;
        case 2:
            return `${n}nd`;
        case 3:
            return `${n}rd`;
        default:
            return `${n}th`;
    }
};

/**
 * Describe a cron expression in plain English. Returns null when the
 * expression uses features we don't translate (ranges, month restrictions,
 * mixed day-of-month + day-of-week, etc.), so callers can fall back to the
 * raw expression.
 */
const describeCron = (cron: string): string | null => {
    const parts = cron.trim().split(/\s+/);
    if (parts.length !== 5) return null;
    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // We only translate presets when month is unrestricted and minute
    // is either a single value or a step pattern.
    if (month !== "*") return null;
    if (minute.includes("-") || minute.includes(",")) return null;

    // Minute-level step: "*/N * * * *"
    if (minute.startsWith("*/") && hour === "*" && dayOfMonth === "*" && dayOfWeek === "*") {
        const interval = parseInt(minute.substring(2), 10);
        if (!isNaN(interval) && interval > 0) {
            return interval === 1 ? "Every minute" : `Every ${interval} minutes`;
        }
        return null;
    }

    // Hourly step: "M */N * * *"
    if (hour.startsWith("*/") && dayOfMonth === "*" && dayOfWeek === "*") {
        const interval = parseInt(hour.substring(2), 10);
        if (isNaN(interval) || interval <= 0) return null;
        if (minute === "0") return interval === 1 ? "Every hour" : `Every ${interval} hours`;
        const m = parseInt(minute, 10);
        if (isNaN(m)) return null;
        const offset = `:${String(m).padStart(2, "0")}`;
        return interval === 1 ? `Every hour at ${offset}` : `Every ${interval} hours at ${offset}`;
    }

    const m = parseInt(minute, 10);
    const h = parseInt(hour, 10);
    if (isNaN(m) || isNaN(h) || h < 0 || h > 23 || m < 0 || m > 59) return null;
    const timeStr = formatTime12h(h, m);

    // Weekly: specific day(s) of week
    if (dayOfWeek !== "*" && dayOfMonth === "*") {
        const days = dayOfWeek.split(",").map(d => parseInt(d, 10));
        if (days.some(isNaN) || days.some(d => d < 0 || d > 6)) return null;
        const sorted = [...new Set(days)].sort((a, b) => a - b);
        if (sorted.length === 7) return `Every day at ${timeStr}`;
        if (sorted.length === 5 && sorted.join(",") === "1,2,3,4,5") return `Weekdays at ${timeStr}`;
        if (sorted.length === 2 && sorted.join(",") === "0,6") return `Weekends at ${timeStr}`;
        if (sorted.length === 1) return `Every ${DAY_NAMES_LONG[sorted[0]]} at ${timeStr}`;
        return `${sorted.map(d => DAY_NAMES_SHORT[d]).join(", ")} at ${timeStr}`;
    }

    // Monthly: specific day of month
    if (dayOfMonth !== "*" && dayOfWeek === "*") {
        const day = parseInt(dayOfMonth, 10);
        if (isNaN(day) || day < 1 || day > 31) return null;
        return `Monthly on the ${ordinal(day)} at ${timeStr}`;
    }

    // Daily
    if (dayOfMonth === "*" && dayOfWeek === "*") return `Every day at ${timeStr}`;

    return null;
};

/**
 * Describe any schedule expression (cron, interval, or one_time) in plain
 * English. Falls back to the raw expression when it can't be translated.
 */
export const describeScheduleExpression = (type: string, expression: string): string => {
    if (!expression) return "Not set";

    if (type === "cron") {
        return describeCron(expression) ?? expression;
    }

    if (type === "interval") {
        const match = /^(\d+)([smhd])$/i.exec(expression.trim());
        if (!match) return expression;
        const n = parseInt(match[1], 10);
        const unitMap: Record<string, [string, string]> = {
            s: ["second", "seconds"],
            m: ["minute", "minutes"],
            h: ["hour", "hours"],
            d: ["day", "days"],
        };
        const [singular, plural] = unitMap[match[2].toLowerCase()];
        return n === 1 ? `Every ${singular}` : `Every ${n} ${plural}`;
    }

    if (type === "one_time") {
        const date = new Date(expression);
        if (isNaN(date.getTime())) return expression;
        return date.toLocaleString(undefined, {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
    }

    return expression;
};

/**
 * Convert a scheduled task's schedule configuration into a human-readable string.
 * Accepts any object with `scheduleType` + `scheduleExpression` so this also
 * works on per-execution snapshots.
 */
export const formatSchedule = (task: { scheduleType: ScheduledTask["scheduleType"]; scheduleExpression: string }): string => {
    if (task.scheduleType === "cron") {
        const cron = task.scheduleExpression;
        const parts = cron.trim().split(/\s+/);

        if (parts.length === 5) {
            const [minute, hour, dayOfMonth, , dayOfWeek] = parts;

            // Hourly pattern (e.g., "0 */6 * * *")
            if (hour.includes("/")) {
                const interval = hour.split("/")[1];
                return `Every ${interval} hours`;
            }

            // Weekly pattern (e.g., "0 9 * * 1,3,5")
            if (dayOfWeek !== "*") {
                const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
                const days = dayOfWeek
                    .split(",")
                    .map(d => dayNames[parseInt(d)])
                    .join(", ");
                const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
                return `${days} at ${time}`;
            }

            // Monthly pattern (e.g., "0 9 15 * *")
            if (dayOfMonth !== "*") {
                const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
                return `Monthly on day ${dayOfMonth} at ${time}`;
            }

            // Daily pattern (e.g., "0 9 * * *")
            if (hour !== "*" && minute !== "*") {
                const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
                return `Daily at ${time}`;
            }
        }

        return `Cron: ${cron}`;
    } else if (task.scheduleType === "interval") {
        return `Every ${task.scheduleExpression}`;
    } else {
        try {
            const date = new Date(task.scheduleExpression);
            const formatted = date.toLocaleString("en-US", {
                weekday: "short",
                year: "numeric",
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
            });
            return `One time: ${formatted}`;
        } catch {
            return `One time: ${task.scheduleExpression}`;
        }
    }
};
