import * as React from "react";
import { cn } from "@/lib/utils";
import { Textarea } from "./textarea";
import { FieldFooter } from "./field-footer";

interface ValidatedTextareaWithFooterProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    maxLength: number;
    validationMessage?: string;
}

const ValidatedTextareaWithFooter = React.forwardRef<HTMLTextAreaElement, ValidatedTextareaWithFooterProps>(({ className, value, maxLength, validationMessage, ...props }, ref) => {
    const textValue = typeof value === "string" ? value : "";
    const isOverLimit = textValue.length > maxLength;
    const defaultMessage = `Description must be less than ${maxLength} characters`;

    return (
        <>
            <Textarea ref={ref} className={cn("resize-none text-sm", isOverLimit && "border-destructive", className)} value={value} maxLength={maxLength + 1} {...props} />
            <FieldFooter hasError={isOverLimit}>{isOverLimit ? validationMessage || defaultMessage : `${textValue.length} / ${maxLength}`}</FieldFooter>
        </>
    );
});

ValidatedTextareaWithFooter.displayName = "ValidatedTextareaWithFooter";

export { ValidatedTextareaWithFooter };
export type { ValidatedTextareaWithFooterProps };
