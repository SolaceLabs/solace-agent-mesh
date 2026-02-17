import React from "react";

export interface PageCitationItemProps {
    pageLabel: string;
    citationCount: number;
}

/**
 * Individual page row within a document card
 * Displays page label and citation count
 * Colors from Figma: title #273749, subtitle #647481
 */
export const PageCitationItem: React.FC<PageCitationItemProps> = ({ pageLabel, citationCount }) => {
    return (
        <div className="flex items-center gap-2 py-2.5">
            <span className="dark:text-foreground min-w-[60px] text-sm font-semibold">{pageLabel}</span>
            <span className="dark:text-muted-foreground text-sm">
                {citationCount} citation{citationCount !== 1 ? "s" : ""}
            </span>
        </div>
    );
};
