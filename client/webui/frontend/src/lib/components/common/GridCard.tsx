import { cn } from "@/lib/utils";
import { Card } from "@/lib/components/ui/card";
import type { ComponentProps } from "react";

interface GridCardProps extends ComponentProps<typeof Card> {
    isSelected?: boolean;
    onClick?: () => void;
}

export const GridCard = ({ children, className, isSelected, onClick, ...props }: GridCardProps) => {
    return (
        <Card noPadding onCardSelect={onClick} isCardSelected={isSelected} className={cn("flex h-40 w-full shrink-0 gap-3 py-3 sm:h-50 sm:w-95 sm:gap-5 sm:py-4", className)} {...props}>
            {children}
        </Card>
    );
};
