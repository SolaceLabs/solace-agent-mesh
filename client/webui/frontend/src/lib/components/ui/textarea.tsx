import * as React from "react";
import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => {
    return <textarea className={cn(`flex min-h-[80px] w-full rounded-md border px-3 py-2 placeholder:opacity-75 disabled:cursor-not-allowed disabled:opacity-50`, className)} ref={ref} {...props} />;
});
Textarea.displayName = "Textarea";

export { Textarea };
