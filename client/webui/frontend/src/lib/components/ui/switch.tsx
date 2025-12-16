import { cn } from "@/lib/utils";

interface SwitchProps {
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
    disabled?: boolean;
    className?: string;
}

function Switch({ checked = false, onCheckedChange, disabled = false, className }: SwitchProps) {
    const handleClick = () => {
        if (!disabled && onCheckedChange) {
            onCheckedChange(!checked);
        }
    };

    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            disabled={disabled}
            onClick={handleClick}
            className={cn(
                "peer focus-visible:ring-ring focus-visible:ring-offset-background inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
                checked ? "bg-primary" : "bg-primary/50",
                className
            )}
        >
            <span className={cn("bg-background pointer-events-none block h-5 w-5 rounded-full shadow-lg ring-0 transition-transform", checked ? "translate-x-5" : "translate-x-0")} />
        </button>
    );
}

export { Switch };
