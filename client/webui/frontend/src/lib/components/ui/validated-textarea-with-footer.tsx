import * as React from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "./textarea";

interface ValidatedTextareaWithFooterProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    /** Maximum character length before showing validation error */
    maxLength: number;
    /** Custom validation message when over limit */
    validationMessage?: string;
}

const ValidatedTextareaWithFooter = React.forwardRef<HTMLTextAreaElement, ValidatedTextareaWithFooterProps>(({ className, value, maxLength, validationMessage, ...props }, ref) => {
    const textValue = typeof value === "string" ? value : "";
    const isOverLimit = textValue.length > maxLength;
    const defaultMessage = `Description must be less than ${maxLength} characters`;

    return (
        <>
            <Textarea ref={ref} className={cn("resize-none text-sm", isOverLimit && "border-destructive", className)} value={value} maxLength={maxLength + 1} {...props} />
            <div className={cn("text-xs", isOverLimit ? "text-destructive" : "text-muted-foreground text-right")}>
                {isOverLimit && (validationMessage || defaultMessage)}
                {!isOverLimit && `${textValue.length} / ${maxLength}`}
            </div>
        </>
    );
});

ValidatedTextareaWithFooter.displayName = "ValidatedTextareaWithFooter";

export { ValidatedTextareaWithFooter };
export type { ValidatedTextareaWithFooterProps };
