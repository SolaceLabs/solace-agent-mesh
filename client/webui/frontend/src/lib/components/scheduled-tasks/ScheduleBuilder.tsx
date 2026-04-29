/**
 * Schedule Builder Component
 * Calendar-style schedule builder
 */

import { useState, useEffect, useRef } from "react";
import { CheckCircle2, ChevronDown, X } from "lucide-react";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { Popover, PopoverAnchor, PopoverContent, PopoverTrigger, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { describeScheduleExpression } from "./utils";

const DAY_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// Multi-select picker for days of the week. Trigger shows selected days as
// removable chips with a chevron; clicking opens a popover with a checkable
// list of all days.
const DaysOfWeekPicker: React.FC<{ selected: number[]; onChange: (days: number[]) => void }> = ({ selected, onChange }) => {
    const [open, setOpen] = useState(false);
    const sorted = [...selected].sort((a, b) => a - b);
    const toggle = (idx: number) => {
        onChange(selected.includes(idx) ? selected.filter(d => d !== idx) : [...selected, idx]);
    };
    const remove = (idx: number) => {
        onChange(selected.filter(d => d !== idx));
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <button type="button" className="flex min-h-[2.5rem] w-full items-center gap-2 rounded-xs border bg-transparent px-2 py-1 text-left text-sm shadow-xs transition-colors outline-none focus-visible:border-(--brand-wMain)">
                    <div className="flex flex-1 flex-wrap items-center gap-1">
                        {sorted.length === 0 ? (
                            <span className="px-1 text-(--secondary-wMain)">Select days</span>
                        ) : (
                            sorted.map(idx => (
                                <span key={idx} className="inline-flex items-center gap-1 rounded-sm bg-(--secondary-w20) px-2 py-0.5 text-xs">
                                    {DAY_LABELS[idx]}
                                    <span
                                        role="button"
                                        tabIndex={0}
                                        onClick={e => {
                                            e.stopPropagation();
                                            remove(idx);
                                        }}
                                        onKeyDown={e => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                remove(idx);
                                            }
                                        }}
                                        aria-label={`Remove ${DAY_LABELS[idx]}`}
                                        className="cursor-pointer rounded-full p-0.5 hover:bg-(--secondary-w40)"
                                    >
                                        <X className="h-3 w-3" />
                                    </span>
                                </span>
                            ))
                        )}
                    </div>
                    <ChevronDown className="h-4 w-4 flex-shrink-0 opacity-50" />
                </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-(--radix-popover-trigger-width) p-1">
                <div className="flex flex-col">
                    {DAY_LABELS.map((label, idx) => {
                        const isSelected = selected.includes(idx);
                        return (
                            <button key={idx} type="button" onClick={() => toggle(idx)} className={`flex items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-(--secondary-w10) ${isSelected ? "font-medium" : ""}`}>
                                <span>{label}</span>
                                {isSelected && <CheckCircle2 className="h-4 w-4 text-(--primary-wMain)" />}
                            </button>
                        );
                    })}
                </div>
            </PopoverContent>
        </Popover>
    );
};

// Format an HH:MM (24h) string as a user-facing 12h string, e.g. "9:30 AM".
function formatTime12h(hour24: number, minute: number): string {
    const period = hour24 >= 12 ? "PM" : "AM";
    const hour12 = hour24 % 12 || 12;
    return `${hour12}:${String(minute).padStart(2, "0")} ${period}`;
}

// Parse a free-typed 12h time, e.g. "9:30 AM", "12:00pm", "1:5 PM" → {hour24, minute}.
// Returns null on anything we can't unambiguously interpret.
function parseTime12h(input: string): { hour24: number; minute: number } | null {
    const trimmed = input.trim().toUpperCase();
    const match = /^(\d{1,2}):(\d{1,2})\s*(AM|PM)$/.exec(trimmed);
    if (!match) return null;
    const h12 = parseInt(match[1], 10);
    const m = parseInt(match[2], 10);
    const period = match[3];
    if (h12 < 1 || h12 > 12 || m < 0 || m > 59) return null;
    let hour24 = h12 % 12;
    if (period === "PM") hour24 += 12;
    return { hour24, minute: m };
}

// 30-minute step options spanning midnight → 11:30 PM (48 entries).
const TIME_OF_DAY_OPTIONS = Array.from({ length: 48 }, (_, i) => {
    const hour24 = Math.floor(i / 2);
    const minute = (i % 2) * 30;
    return { hour24, minute, label: formatTime12h(hour24, minute) };
});

// Single-field time picker styled like a Select. Users can either click the
// chevron to pick a 30-minute step from the popover, or type any specific
// time (validated as `H:MM AM/PM`). Invalid input on blur reverts to the
// last valid value so the parent never sees a malformed time.
export const TimeOfDayPicker: React.FC<{ value: string; onChange: (hhmm: string) => void; invalid?: boolean }> = ({ value, onChange, invalid }) => {
    const [open, setOpen] = useState(false);
    const [parts, setParts] = useState(() => value.split(":").map(Number));
    const initialDisplay = !isNaN(parts[0]) && !isNaN(parts[1]) ? formatTime12h(parts[0], parts[1]) : "9:00 AM";
    const [draft, setDraft] = useState(initialDisplay);
    const inputRef = useRef<HTMLInputElement>(null);

    // Sync draft when the parent's value changes (e.g. AI builder updated it,
    // or user opened an existing task).
    useEffect(() => {
        const [h, m] = value.split(":").map(Number);
        if (!isNaN(h) && !isNaN(m)) {
            setParts([h, m]);
            setDraft(formatTime12h(h, m));
        }
    }, [value]);

    const commit = () => {
        const parsed = parseTime12h(draft);
        if (parsed) {
            const hhmm = `${String(parsed.hour24).padStart(2, "0")}:${String(parsed.minute).padStart(2, "0")}`;
            setDraft(formatTime12h(parsed.hour24, parsed.minute));
            if (hhmm !== value) onChange(hhmm);
        } else {
            // Revert to last valid value rather than silently emitting garbage.
            const [h, m] = parts;
            setDraft(formatTime12h(h || 9, m || 0));
        }
    };

    const pick = (hour24: number, minute: number) => {
        const hhmm = `${String(hour24).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
        setDraft(formatTime12h(hour24, minute));
        setParts([hour24, minute]);
        onChange(hhmm);
        setOpen(false);
        inputRef.current?.blur();
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverAnchor asChild>
                <div className={`relative inline-flex w-[8rem] items-center rounded-xs border bg-transparent shadow-xs transition-colors focus-within:border-(--brand-wMain) ${invalid ? "border-(--error-w100)" : ""}`}>
                    <input
                        ref={inputRef}
                        type="text"
                        className="w-full bg-transparent py-2 pr-8 pl-3 text-sm outline-none"
                        value={draft}
                        onChange={e => setDraft(e.target.value)}
                        onBlur={commit}
                        onKeyDown={e => {
                            if (e.key === "Enter") {
                                e.preventDefault();
                                commit();
                                setOpen(false);
                            } else if (e.key === "Escape") {
                                setOpen(false);
                            } else if (e.key === "ArrowDown" && !open) {
                                e.preventDefault();
                                setOpen(true);
                            }
                        }}
                    />
                    <PopoverTrigger asChild>
                        <button type="button" tabIndex={-1} aria-label="Open time options" className="absolute right-2 flex h-6 w-6 items-center justify-center text-(--secondary-text-wMain) opacity-50 hover:opacity-100">
                            <ChevronDown className="h-4 w-4" />
                        </button>
                    </PopoverTrigger>
                </div>
            </PopoverAnchor>
            <PopoverContent align="start" sideOffset={4} className="max-h-[16rem] w-(--radix-popover-trigger-width) overflow-y-auto p-1" onOpenAutoFocus={e => e.preventDefault()}>
                <div className="flex flex-col">
                    {TIME_OF_DAY_OPTIONS.map(opt => {
                        const isSelected = parts[0] === opt.hour24 && parts[1] === opt.minute;
                        return (
                            <button key={opt.label} type="button" onClick={() => pick(opt.hour24, opt.minute)} className={`rounded-sm px-2 py-1.5 text-left text-sm hover:bg-(--secondary-w10) ${isSelected ? "font-medium" : ""}`}>
                                {opt.label}
                            </button>
                        );
                    })}
                </div>
            </PopoverContent>
        </Popover>
    );
};

// Light-gray "Preview" box rendered below schedule controls so the user can
// see the human-readable cadence as they tweak inputs. Same look-and-feel as
// the AI builder's TaskPreviewPanel preview.
export const SchedulePreviewBox: React.FC<{ description: string }> = ({ description }) => (
    <div className="rounded-md bg-(--background-w10) px-3 py-2">
        <p className="text-xs text-(--secondary-text-wMain)">Preview</p>
        <p className="mt-0.5 text-sm">{description}</p>
    </div>
);

// Schedule builder types
type FrequencyType = "daily" | "weekly" | "monthly" | "custom";

// Nth occurrence within a month: "1"=First, "2"=Second, "3"=Third, "4"=Fourth, "L"=Last.
type MonthNth = "1" | "2" | "3" | "4" | "L";

const MONTH_NTH_LABELS: Record<MonthNth, string> = {
    "1": "First",
    "2": "Second",
    "3": "Third",
    "4": "Fourth",
    L: "Last",
};

interface ScheduleConfig {
    frequency: FrequencyType;
    time: string; // HH:MM format
    ampm: "AM" | "PM";
    weekDays: number[]; // 0-6 (Sunday-Saturday)
    monthNth: MonthNth; // which occurrence of the chosen weekday in the month
    monthWeekday: number; // 0-6 (Sunday-Saturday)
}

// Convert schedule config to cron expression
function scheduleToCron(config: ScheduleConfig): string {
    const parts = config.time.split(":");
    const hours12 = Number(parts[0]);
    const minutes = Number(parts[1]);

    // Guard against partial/invalid time input producing NaN in cron
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
            const days = config.weekDays.sort().join(",");
            return `${minutes} ${hour} * * ${days}`;
        }

        case "monthly": {
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
function normalizeCron(cron: string): string {
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
function cronToSchedule(cron: string): ScheduleConfig | null {
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
        monthNth: "1",
        monthWeekday: 1,
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
        candidate = { frequency: "monthly", time, ampm, weekDays: [], monthNth: nStr as MonthNth, monthWeekday: wd };
    } else if (dayOfMonth === "*" && /^\dL$/i.test(dayOfWeek)) {
        // Last weekday of month, e.g. "5L" = last Friday.
        const wd = parseInt(dayOfWeek[0]);
        if (wd < 0 || wd > 6) return customFallback;
        candidate = { frequency: "monthly", time, ampm, weekDays: [], monthNth: "L", monthWeekday: wd };
    } else if (dayOfWeek !== "*" && /^\d+(,\d+)*$/.test(dayOfWeek)) {
        const days = dayOfWeek.split(",").map(d => parseInt(d));
        candidate = { frequency: "weekly", time, ampm, weekDays: days, monthNth: "1", monthWeekday: 1 };
    } else if (dayOfMonth === "*" && dayOfWeek === "*") {
        candidate = { frequency: "daily", time, ampm, weekDays: [], monthNth: "1", monthWeekday: 1 };
    } else {
        // Anything else (plain day-of-month, ranges, lists in dayOfMonth, etc.)
        // doesn't fit the Nth-weekday Monthly preset — fall back to Custom.
        return customFallback;
    }

    // If the preset candidate doesn't roundtrip to the input, the cron has
    // structure we can't represent — keep the original as a custom expression.
    if (normalizeCron(scheduleToCron(candidate)) !== normalizeCron(cron)) {
        return customFallback;
    }
    return candidate;
}

// Helper function to generate human-readable schedule description
function getScheduleDescription(config: ScheduleConfig): string {
    const timeStr = `${config.time} ${config.ampm}`;

    switch (config.frequency) {
        case "daily":
            return `Every day at ${timeStr}`;

        case "weekly": {
            if (config.weekDays.length === 0) return `Every day at ${timeStr}`;
            const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
            const days = config.weekDays
                .sort()
                .map(d => dayNames[d])
                .join(", ");
            return `Every ${days} at ${timeStr}`;
        }

        case "monthly": {
            const dayName = DAY_LABELS[config.monthWeekday] || "Monday";
            const ordinal = MONTH_NTH_LABELS[config.monthNth].toLowerCase();
            return `${ordinal === "last" ? "Last" : ordinal[0].toUpperCase() + ordinal.slice(1)} ${dayName} of every month at ${timeStr}`;
        }

        default:
            return "Custom schedule";
    }
}

// Validate cron expression
function validateCron(cron: string): { valid: boolean; error?: string } {
    const trimmed = cron.trim();
    if (!trimmed) {
        return { valid: false, error: "Cron expression cannot be empty" };
    }

    const parts = trimmed.split(/\s+/);
    if (parts.length !== 5) {
        return { valid: false, error: "Cron expression must have exactly 5 fields (minute hour day month weekday)" };
    }

    const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

    // Validate minute (0-59)
    if (!isValidCronField(minute, 0, 59)) {
        return { valid: false, error: "Invalid minute field (must be 0-59 or * or */n)" };
    }

    // Validate hour (0-23)
    if (!isValidCronField(hour, 0, 23)) {
        return { valid: false, error: "Invalid hour field (must be 0-23 or * or */n)" };
    }

    // Validate day of month (1-31)
    if (!isValidCronField(dayOfMonth, 1, 31)) {
        return { valid: false, error: "Invalid day of month field (must be 1-31 or * or */n)" };
    }

    // Validate month (1-12)
    if (!isValidCronField(month, 1, 12)) {
        return { valid: false, error: "Invalid month field (must be 1-12 or * or */n)" };
    }

    // Validate day of week (0-6)
    if (!isValidCronField(dayOfWeek, 0, 6)) {
        return { valid: false, error: "Invalid day of week field (must be 0-6 or * or */n)" };
    }

    return { valid: true };
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

export function ScheduleBuilder({ value, onChange }: { value: string; onChange: (cron: string) => void }) {
    const [rawCron, setRawCron] = useState(value);
    const [cronValidation, setCronValidation] = useState<{ valid: boolean; error?: string }>({ valid: true });

    // Stabilize onChange via ref to avoid re-triggering the effect on every render
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;

    // Initialize schedule config from cron or use defaults
    const initialConfig: ScheduleConfig = cronToSchedule(value) || {
        frequency: "daily",
        time: "09:00",
        ampm: "AM",
        weekDays: [],
        monthNth: "1",
        monthWeekday: 1,
    };

    const [config, setConfig] = useState<ScheduleConfig>(initialConfig);

    // Sync internal state when the `value` prop changes externally
    // (e.g. when the parent populates an existing task for editing).
    useEffect(() => {
        if (config.frequency === "custom") {
            setRawCron(value);
            return;
        }
        if (value === scheduleToCron(config)) return;
        const parsed = cronToSchedule(value);
        if (parsed) {
            setConfig(parsed);
            setRawCron(value);
        }
    }, [value]);

    // Update cron when config changes (except in custom mode)
    useEffect(() => {
        if (config.frequency !== "custom") {
            const newCron = scheduleToCron(config);
            setRawCron(newCron);
            onChangeRef.current(newCron);
        }
    }, [config]);

    // Handle custom cron changes
    const handleRawCronChange = (newCron: string) => {
        setRawCron(newCron);
        const validation = validateCron(newCron);
        setCronValidation(validation);

        // Only propagate valid cron expressions
        if (validation.valid) {
            onChangeRef.current(newCron);
        }
    };

    const updateConfig = (updates: Partial<ScheduleConfig>) => {
        // When switching from custom mode to another frequency, try to parse the current cron
        if (config.frequency === "custom" && updates.frequency && updates.frequency !== "custom") {
            const parsedConfig = cronToSchedule(rawCron);
            if (parsedConfig) {
                // Merge the parsed config with the frequency update
                setConfig({ ...parsedConfig, ...updates });
                return;
            }
        }

        // When switching from manual mode to custom mode, preserve the current cron expression
        if (config.frequency !== "custom" && updates.frequency === "custom") {
            const currentCron = scheduleToCron(config);
            setRawCron(currentCron);
            // Validate the generated cron
            const validation = validateCron(currentCron);
            setCronValidation(validation);
        }

        setConfig({ ...config, ...updates });
    };

    // Show custom cron input when frequency is "custom"
    if (config.frequency === "custom") {
        return (
            <div className="space-y-3">
                <div>
                    <label className="mb-2 block text-xs text-(--secondary-text-wMain)">Frequency</label>
                    <Select value={config.frequency} onValueChange={val => updateConfig({ frequency: val as FrequencyType })}>
                        <SelectTrigger className="min-w-[10rem]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="daily">Daily</SelectItem>
                            <SelectItem value="weekly">Weekly</SelectItem>
                            <SelectItem value="monthly">Monthly</SelectItem>
                            <SelectItem value="custom">Custom (Cron Expression)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Match the column width of the Schedule Type dropdown above
                    (which lives in a `grid-cols-2` container) so the inputs
                    line up vertically. */}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="mb-2 block text-sm font-medium">Cron Expression</label>
                        <div className="relative">
                            <input
                                type="text"
                                className={`w-full rounded-xs border px-3 py-2 pr-10 font-mono text-sm ${!cronValidation.valid ? "border-destructive focus:ring-destructive" : ""}`}
                                value={rawCron}
                                onChange={e => handleRawCronChange(e.target.value)}
                                placeholder="0 9 * * *"
                            />
                            {cronValidation.valid && (
                                <div className="absolute top-1/2 right-3 -translate-y-1/2">
                                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                                </div>
                            )}
                        </div>
                        {!cronValidation.valid && cronValidation.error ? (
                            <MessageBanner variant="error" message={cronValidation.error} className="mt-2" />
                        ) : (
                            <p className="mt-1 text-xs text-(--secondary-text-wMain)">
                                Format: <span className="font-mono">minute hour day month weekday</span>
                            </p>
                        )}
                    </div>
                </div>

                {cronValidation.valid && rawCron.trim() && <SchedulePreviewBox description={describeScheduleExpression("cron", rawCron)} />}

                {/* Syntax Guide */}
                <div className="space-y-2 rounded-lg bg-(--secondary-w10) p-3">
                    <p className="text-xs font-semibold text-(--secondary-text-wMain)">Common Examples:</p>
                    <div className="space-y-1 font-mono text-xs">
                        <div className="flex justify-between">
                            <span className="text-(--primary-wMain)">0 9 * * *</span>
                            <span className="text-(--secondary-text-wMain)">Every day at 9:00 AM</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-(--primary-wMain)">0 */6 * * *</span>
                            <span className="text-(--secondary-text-wMain)">Every 6 hours</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-(--primary-wMain)">0 9 * * 1</span>
                            <span className="text-(--secondary-text-wMain)">Every Monday at 9:00 AM</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-(--primary-wMain)">0 0 1 * *</span>
                            <span className="text-(--secondary-text-wMain)">First day of month at midnight</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-(--primary-wMain)">*/15 * * * *</span>
                            <span className="text-(--secondary-text-wMain)">Every 15 minutes</span>
                        </div>
                    </div>
                    <p className="mt-2 text-xs text-(--secondary-text-wMain)">
                        Use <span className="font-mono">*</span> for "any", <span className="font-mono">,</span> for lists, <span className="font-mono">-</span> for ranges, <span className="font-mono">/</span> for intervals
                    </p>
                </div>
            </div>
        );
    }

    // Simple mode (default)
    const time24 = (() => {
        const parts = config.time.split(":");
        const h12 = Number(parts[0]);
        const m = Number(parts[1]);
        if (isNaN(h12) || isNaN(m)) return "09:00";
        let h24 = h12;
        if (config.ampm === "PM") h24 = h12 === 12 ? 12 : h12 + 12;
        else if (config.ampm === "AM") h24 = h12 === 12 ? 0 : h12;
        return `${String(h24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    })();

    return (
        <div className="space-y-4">
            {/* Frequency + Time + per-frequency day picker, all on one row.
                Wraps on narrow viewports so nothing overflows. */}
            <div className="flex flex-wrap items-end gap-3">
                <div>
                    <label className="mb-2 block text-xs text-(--secondary-text-wMain)">Frequency</label>
                    <Select value={config.frequency} onValueChange={val => updateConfig({ frequency: val as FrequencyType })}>
                        <SelectTrigger className="min-w-[10rem]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="daily">Daily</SelectItem>
                            <SelectItem value="weekly">Weekly</SelectItem>
                            <SelectItem value="monthly">Monthly</SelectItem>
                            <SelectItem value="custom">Custom (Cron Expression)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div>
                    <label className="mb-2 block text-xs text-(--secondary-text-wMain)">Time</label>
                    <TimeOfDayPicker
                        value={time24}
                        onChange={val => {
                            const [h24, m] = val.split(":").map(Number);
                            const ampm: "AM" | "PM" = h24 >= 12 ? "PM" : "AM";
                            const h12 = h24 % 12 || 12;
                            updateConfig({
                                time: `${String(h12).padStart(2, "0")}:${String(m).padStart(2, "0")}`,
                                ampm,
                            });
                        }}
                    />
                </div>

                {config.frequency === "monthly" && (
                    <>
                        <div>
                            <label className="mb-2 block text-xs text-(--secondary-text-wMain)">Day</label>
                            <Select value={config.monthNth} onValueChange={val => updateConfig({ monthNth: val as MonthNth })}>
                                <SelectTrigger className="min-w-[7rem]">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {(Object.keys(MONTH_NTH_LABELS) as MonthNth[]).map(key => (
                                        <SelectItem key={key} value={key}>
                                            {MONTH_NTH_LABELS[key]}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div>
                            {/* Pairs with the "Day" dropdown above — no separate label
                                so the two ordinal+weekday selects read as one phrase. */}
                            <label className="mb-2 block text-xs text-(--secondary-text-wMain)">&nbsp;</label>
                            <Select value={String(config.monthWeekday)} onValueChange={val => updateConfig({ monthWeekday: parseInt(val) })}>
                                <SelectTrigger className="min-w-[8rem]">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {DAY_LABELS.map((dayName, idx) => (
                                        <SelectItem key={idx} value={String(idx)}>
                                            {dayName}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </>
                )}

                {config.frequency === "weekly" && (
                    <div className="min-w-[18rem] flex-1">
                        <label className="mb-2 block text-xs text-(--secondary-text-wMain)">Days of the Week</label>
                        <DaysOfWeekPicker selected={config.weekDays} onChange={days => updateConfig({ weekDays: days })} />
                    </div>
                )}
            </div>

            {/* Daily is trivial enough not to need a preview — show only for the
                multi-field frequencies (weekly with day picks, monthly with day-of-month). */}
            {config.frequency !== "daily" && <SchedulePreviewBox description={getScheduleDescription(config)} />}
        </div>
    );
}
