import { useState, useMemo } from "react";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

// Visual labels are intentionally single-letter to match the design mock,
// but "S"/"T" are ambiguous (Sun/Sat, Tue/Thu) so we pair each with a full
// aria-label for screen-reader users. Keep `letter` and `label` index-aligned.
const DAYS_OF_WEEK = [
    { letter: "S", label: "Sunday" },
    { letter: "M", label: "Monday" },
    { letter: "T", label: "Tuesday" },
    { letter: "W", label: "Wednesday" },
    { letter: "T", label: "Thursday" },
    { letter: "F", label: "Friday" },
    { letter: "S", label: "Saturday" },
];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function getDaysInMonth(year: number, month: number): number {
    return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
    return new Date(year, month, 1).getDay();
}

function formatDate(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function parseDate(value: string): Date | null {
    if (!value) return null;
    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) return null;
    const date = new Date(year, month - 1, day);
    return isNaN(date.getTime()) ? null : date;
}

interface DatePickerProps {
    value: string; // YYYY-MM-DD
    onChange: (value: string) => void;
    min?: string; // YYYY-MM-DD
    placeholder?: string;
    className?: string;
    invalid?: boolean;
}

function DatePicker({ value, onChange, min, placeholder = "Pick a date", className, invalid }: DatePickerProps) {
    const [open, setOpen] = useState(false);
    const selectedDate = parseDate(value);
    const minDate = parseDate(min ?? "");

    const today = useMemo(() => {
        const d = new Date();
        d.setHours(0, 0, 0, 0);
        return d;
    }, []);

    const [viewYear, setViewYear] = useState(() => selectedDate?.getFullYear() ?? today.getFullYear());
    const [viewMonth, setViewMonth] = useState(() => selectedDate?.getMonth() ?? today.getMonth());

    const daysInMonth = getDaysInMonth(viewYear, viewMonth);
    const firstDay = getFirstDayOfMonth(viewYear, viewMonth);

    const prevMonth = () => {
        if (viewMonth === 0) {
            setViewMonth(11);
            setViewYear(y => y - 1);
        } else {
            setViewMonth(m => m - 1);
        }
    };

    const nextMonth = () => {
        if (viewMonth === 11) {
            setViewMonth(0);
            setViewYear(y => y + 1);
        } else {
            setViewMonth(m => m + 1);
        }
    };

    const isDisabled = (day: number) => {
        if (!minDate) return false;
        const date = new Date(viewYear, viewMonth, day);
        date.setHours(0, 0, 0, 0);
        return date < minDate;
    };

    const isSelected = (day: number) => {
        if (!selectedDate) return false;
        return selectedDate.getFullYear() === viewYear && selectedDate.getMonth() === viewMonth && selectedDate.getDate() === day;
    };

    const isToday = (day: number) => {
        return today.getFullYear() === viewYear && today.getMonth() === viewMonth && today.getDate() === day;
    };

    const handleSelect = (day: number) => {
        const date = new Date(viewYear, viewMonth, day);
        onChange(formatDate(date));
        setOpen(false);
    };

    // Display in the same YYYY-MM-DD form used internally and elsewhere in
    // the app, so the trigger text matches the rest of the page (e.g.,
    // execution timestamps).
    const displayValue = selectedDate ? formatDate(selectedDate) : null;

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="outline" className={cn("justify-between gap-2 font-normal", !value && "text-(--secondary-text-wMain)", invalid && "border-red-500", className)}>
                    <span className="truncate">{displayValue ?? placeholder}</span>
                    <span className="flex items-center gap-1">
                        {value && (
                            // Span (not <button>) because the wrapping element
                            // is already a <button> popover trigger and nested
                            // buttons are invalid HTML. We add explicit
                            // keyboard support so Enter/Space clear the date,
                            // matching real button semantics for a11y users.
                            <span
                                role="button"
                                tabIndex={0}
                                aria-label="Clear date"
                                onClick={e => {
                                    e.stopPropagation();
                                    onChange("");
                                }}
                                onKeyDown={e => {
                                    if (e.key === "Enter" || e.key === " ") {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        onChange("");
                                    }
                                }}
                                className="flex h-5 w-5 items-center justify-center rounded hover:bg-(--secondary-w20) focus-visible:ring-2 focus-visible:ring-(--brand-wMain) focus-visible:outline-none"
                            >
                                <X className="h-3.5 w-3.5 text-(--secondary-text-wMain)" />
                            </span>
                        )}
                        <CalendarIcon className="h-4 w-4 text-(--secondary-text-wMain)" />
                    </span>
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3" align="start">
                {/* Month/Year on the left, prev/next chevrons on the right */}
                <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium">
                        {MONTHS[viewMonth]} {viewYear}
                    </span>
                    <div className="flex items-center gap-1">
                        <button type="button" onClick={prevMonth} className="rounded p-1 hover:bg-(--primary-w10)">
                            <ChevronLeftIcon className="h-4 w-4" />
                        </button>
                        <button type="button" onClick={nextMonth} className="rounded p-1 hover:bg-(--primary-w10)">
                            <ChevronRightIcon className="h-4 w-4" />
                        </button>
                    </div>
                </div>

                {/* Day-of-week headers */}
                <div className="grid grid-cols-7 gap-0">
                    {DAYS_OF_WEEK.map(({ letter, label }) => (
                        <div key={label} aria-label={label} className="py-1 text-center text-xs font-medium text-(--secondary-text-wMain)">
                            <span aria-hidden="true">{letter}</span>
                        </div>
                    ))}

                    {/* Empty cells for offset */}
                    {Array.from({ length: firstDay }, (_, i) => (
                        <div key={`empty-${i}`} />
                    ))}

                    {/* Day cells */}
                    {Array.from({ length: daysInMonth }, (_, i) => {
                        const day = i + 1;
                        const disabled = isDisabled(day);
                        const selected = isSelected(day);
                        const todayCell = isToday(day);

                        return (
                            <button
                                key={day}
                                type="button"
                                disabled={disabled}
                                onClick={() => handleSelect(day)}
                                className={cn(
                                    "m-0.5 h-8 w-8 rounded-full text-sm transition-colors",
                                    disabled && "cursor-not-allowed opacity-30",
                                    !disabled && !selected && "hover:bg-(--primary-w10)",
                                    selected && "bg-(--primary-wMain) text-(--primary-text-w10)",
                                    todayCell && !selected && "font-bold"
                                )}
                            >
                                {day}
                            </button>
                        );
                    })}
                </div>
            </PopoverContent>
        </Popover>
    );
}

export { DatePicker };
