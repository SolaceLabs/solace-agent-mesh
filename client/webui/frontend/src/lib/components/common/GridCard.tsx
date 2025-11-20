import { cn } from "@/lib/utils";
import { Card } from "@/lib/components/ui/card";
import type { ComponentProps } from "react";

interface GridCardProps extends ComponentProps<typeof Card> {
    isSelected?: boolean;
    onClick?: () => void;
}

export const GridCard = ({ children, className, isSelected, onClick, ...props }: GridCardProps) => {
    return (
        <Card
            className={cn(
                "flex h-[200px] w-[380px] flex-shrink-0 py-4 transition-all",
                onClick && "cursor-pointer hover:bg-[var(--color-primary-w10)] dark:hover:bg-[var(--color-primary-wMain)]",
                onClick && "focus-visible:border-[var(--color-brand-w100)] focus-visible:outline-none",
                isSelected && "border-[var(--color-brand-w100)]",
                className
            )}
            onClick={onClick}
            onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onClick?.();
                }
            }}
            {...(onClick && { role: "button", tabIndex: 0 })}
            noPadding
            {...props}
        >
            {children}
        </Card>
    );
};
