import * as React from "react";
import { cn } from "@/lib/utils";

interface FieldFooterProps {
    hasError?: boolean;
    align?: "left" | "right";
    className?: string;
    children: React.ReactNode;
}

const FieldFooter: React.FC<FieldFooterProps> = ({ hasError = false, align, className, children }) => {
    const defaultAlign = hasError ? "left" : "right";
    const textAlign = align || defaultAlign;

    return <div className={cn("text-xs", hasError ? "text-destructive" : "text-muted-foreground", textAlign === "right" && "text-right", className)}>{children}</div>;
};

FieldFooter.displayName = "FieldFooter";

export { FieldFooter };
export type { FieldFooterProps };
