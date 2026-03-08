import * as React from "react";
import { cn } from "@/lib/utils";

interface FieldFooterProps {
    hasError?: boolean;
    message: string;
    error: string;
    align?: "left" | "right";
    className?: string;
}

const FieldFooter: React.FC<FieldFooterProps> = ({ hasError = false, message, error, align, className }) => {
    const defaultAlign = hasError ? "left" : "right";
    const textAlign = align || defaultAlign;

    return <div className={cn("text-xs", hasError ? "text-(--color-error-wMain)" : "text-muted-foreground", textAlign === "right" && "text-right", className)}>{hasError ? error : message}</div>;
};

FieldFooter.displayName = "FieldFooter";

export { FieldFooter };
export type { FieldFooterProps };
