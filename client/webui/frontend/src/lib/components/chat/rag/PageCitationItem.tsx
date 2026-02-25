import React from "react";

import { Button } from "@/lib/components/ui/button";

export interface LocationCitationItemProps {
    locationLabel: string;
    citationCount: number;
    onView?: () => void;
}

export const LocationCitationItem: React.FC<LocationCitationItemProps> = ({ locationLabel, citationCount, onView }) => {
    return (
        <div className="flex items-center justify-between py-2.5">
            <div className="flex items-center gap-2">
                <span className="dark:text-foreground min-w-[60px] text-sm font-semibold">{locationLabel}</span>
                <span className="dark:text-muted-foreground text-sm">
                    {citationCount} citation{citationCount !== 1 ? "s" : ""}
                </span>
            </div>
            {onView && (
                <Button variant="link" className="h-auto p-0 text-sm" onClick={onView}>
                    View
                </Button>
            )}
        </div>
    );
};
