import React from "react";

import { Button } from "@/lib/components/ui/button";

export interface LocationCitationItemProps {
    locationLabel: string;
    citationCount: number;
    onView?: () => void;
}

/**
 * Determines the appropriate button text based on the location type.
 * @param locationLabel The location label (e.g., "Page 3", "Lines 1-50", "Slide 5")
 * @returns The button text (e.g., "View Page", "View Lines", "View Slide")
 */
const getViewButtonText = (locationLabel: string): string => {
    if (locationLabel.startsWith("Page")) return "View Page";
    if (locationLabel.startsWith("Lines ")) return "View Lines";
    if (locationLabel.startsWith("Slide")) return "View Slide";
    if (locationLabel.startsWith("Paragraph")) return "View Paragraph";
    return "View";
};

export const LocationCitationItem: React.FC<LocationCitationItemProps> = ({ locationLabel, citationCount, onView }) => {
    const buttonText = getViewButtonText(locationLabel);

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
                    {buttonText}
                </Button>
            )}
        </div>
    );
};
