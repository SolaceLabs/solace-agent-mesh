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
            className={cn("h-[200px] w-[380px] flex-shrink-0 overflow-hidden transition-all", onClick && "hover:bg-accent/50 cursor-pointer", isSelected && "border-[var(--color-brand-w100)]", className)}
            onClick={onClick}
            {...(onClick && { role: "button", tabIndex: 0 })}
            noPadding
            {...props}
        >
            {children}
        </Card>
    );
};
