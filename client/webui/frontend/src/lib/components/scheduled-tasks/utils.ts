import type { ScheduledTask } from "@/lib/types/scheduled-tasks";

/**
 * Convert a scheduled task's schedule configuration into a human-readable string.
 */
export const formatSchedule = (task: ScheduledTask): string => {
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
