import { cn } from "@/lib/utils";
import { Card } from "@/lib/components/ui/card";
import type { ComponentProps } from "react";

interface GridCardProps extends ComponentProps<typeof Card> {
    isSelected?: boolean;
    onClick?: () => void;
}

export const GridCard = ({ children, className, isSelected, onClick, ...props }: GridCardProps) => {
    return (
        <Card noPadding onCardSelect={onClick} isCardSelected={isSelected} className={cn("flex h-50 w-95 shrink-0 py-4", className)} {...props}>
            {children}
        </Card>
    );
};
