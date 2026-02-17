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
            <span className="dark:text-foreground text-sm font-semibold text-[#273749]">{pageLabel}</span>
            <span className="dark:text-muted-foreground text-sm text-[#647481]">
                {citationCount} citation{citationCount !== 1 ? "s" : ""}
            </span>
        </div>
    );
};
