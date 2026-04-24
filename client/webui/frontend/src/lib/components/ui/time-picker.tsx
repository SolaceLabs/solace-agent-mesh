import { ClockIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";

interface TimePickerProps {
    value: string; // HH:MM (24h)
    onChange: (value: string) => void;
    className?: string;
    invalid?: boolean;
}

function to24h(hour12: number, period: "AM" | "PM"): number {
    if (period === "AM") return hour12 === 12 ? 0 : hour12;
    return hour12 === 12 ? 12 : hour12 + 12;
}

function TimePicker({ value, onChange, className, invalid }: TimePickerProps) {
    const [h24, min] = value ? value.split(":").map(Number) : [NaN, NaN];
    const hasValue = !isNaN(h24) && !isNaN(min);

    const hour12 = hasValue ? h24 % 12 || 12 : 9;
    const minute = hasValue ? min : 0;
    const period: "AM" | "PM" = hasValue ? (h24 >= 12 ? "PM" : "AM") : "AM";

    const emit = (newHour12: number, newMinute: number, newPeriod: "AM" | "PM") => {
        const h = to24h(newHour12, newPeriod);
        onChange(`${String(h).padStart(2, "0")}:${String(newMinute).padStart(2, "0")}`);
    };

    return (
        <div className={cn("flex items-center gap-1.5", className)}>
            <ClockIcon className="h-4 w-4 shrink-0 text-(--secondary-text-wMain)" />

            {/* Hour */}
            <Select value={String(hour12)} onValueChange={v => emit(Number(v), minute, period)}>
                <SelectTrigger className={cn("w-[4.5rem]", invalid && "border-red-500")}>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map(h => (
                        <SelectItem key={h} value={String(h)}>
                            {String(h).padStart(2, "0")}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>

            <span className="text-sm font-medium text-(--secondary-text-wMain)">:</span>

            {/* Minute */}
            <Select value={String(minute)} onValueChange={v => emit(hour12, Number(v), period)}>
                <SelectTrigger className={cn("w-[4.5rem]", invalid && "border-red-500")}>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    {Array.from({ length: 60 }, (_, m) => m).map(m => (
                        <SelectItem key={m} value={String(m)}>
                            {String(m).padStart(2, "0")}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>

            {/* AM/PM */}
            <Select value={period} onValueChange={v => emit(hour12, minute, v as "AM" | "PM")}>
                <SelectTrigger className={cn("w-[4.5rem]", invalid && "border-red-500")}>
                    <SelectValue />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="AM">AM</SelectItem>
                    <SelectItem value="PM">PM</SelectItem>
                </SelectContent>
            </Select>
        </div>
    );
}

export { TimePicker };
