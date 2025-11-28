import * as React from "react";

import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
    value?: number;
    max?: number;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(({ className, value = 0, max = 100, ...props }, ref) => {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100));

    return (
        <div ref={ref} className={cn("bg-primary/20 relative h-2 w-full overflow-hidden rounded-full", className)} {...props}>
            <div className="bg-primary h-full transition-all duration-300 ease-in-out" style={{ width: `${percentage}%` }} />
        </div>
    );
});
Progress.displayName = "Progress";

export { Progress };
