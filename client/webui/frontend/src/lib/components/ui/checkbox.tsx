/**
 * Checkbox Component
 * Simple checkbox component for multi-select functionality
 */

import React from "react";
import { Check } from "lucide-react";

interface CheckboxProps {
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
    disabled?: boolean;
    className?: string;
}

export const Checkbox: React.FC<CheckboxProps> = ({ checked = false, onCheckedChange, disabled = false, className = "" }) => {
    const handleClick = () => {
        if (!disabled && onCheckedChange) {
            onCheckedChange(!checked);
        }
    };

    return (
        <button
            type="button"
            role="checkbox"
            aria-checked={checked}
            disabled={disabled}
            onClick={handleClick}
            className={`flex h-5 w-5 items-center justify-center rounded border-2 transition-colors ${
                checked ? "border-(--primary-wMain) bg-(--primary-wMain) text-(--primary-text-w10)" : "bg-(--background-w10) hover:border-(--primary-wMain)"
            } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"} ${className} `}
        >
            {checked && <Check className="h-3 w-3" />}
        </button>
    );
};
