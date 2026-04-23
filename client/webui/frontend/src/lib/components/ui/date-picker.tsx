import { useState, useMemo } from "react";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";

const DAYS_OF_WEEK = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
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

    const displayValue = selectedDate ? selectedDate.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null;

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="outline" className={cn("justify-start gap-2 font-normal", !value && "text-(--secondary-text-wMain)", invalid && "border-red-500", className)}>
                    <CalendarIcon className="h-4 w-4 text-(--secondary-text-wMain)" />
                    {displayValue ?? placeholder}
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-3" align="start">
                {/* Month/Year navigation */}
                <div className="mb-2 flex items-center justify-between">
                    <button type="button" onClick={prevMonth} className="rounded p-1 hover:bg-(--primary-w10)">
                        <ChevronLeftIcon className="h-4 w-4" />
                    </button>
                    <span className="text-sm font-medium">
                        {MONTHS[viewMonth]} {viewYear}
                    </span>
                    <button type="button" onClick={nextMonth} className="rounded p-1 hover:bg-(--primary-w10)">
                        <ChevronRightIcon className="h-4 w-4" />
                    </button>
                </div>

                {/* Day-of-week headers */}
                <div className="grid grid-cols-7 gap-0">
                    {DAYS_OF_WEEK.map(d => (
                        <div key={d} className="py-1 text-center text-xs font-medium text-(--secondary-text-wMain)">
                            {d}
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
                                    "m-0.5 h-8 w-8 rounded text-sm transition-colors",
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
