/**
 * Progress Component
 * Simple progress bar component for showing download/upload progress
 */

import React from "react";

interface ProgressProps {
    value?: number; // 0-100
    className?: string;
}

export const Progress: React.FC<ProgressProps> = ({ value = 0, className = "" }) => {
    const clampedValue = Math.min(100, Math.max(0, value));

    return (
        <div className={`bg-muted relative h-2 w-full overflow-hidden rounded-full ${className}`}>
            <div className="bg-primary h-full transition-all duration-300 ease-in-out" style={{ width: `${clampedValue}%` }} />
        </div>
    );
};
