import React from "react";

export interface PageCitationItemProps {
    pageLabel: string;
    citationCount: number;
    onViewInPage?: () => void; // Placeholder for future functionality
}

/**
 * Individual page row within a document card
 * Displays page label, citation count, and "View in Page" link
 * Colors from Figma: title #273749, subtitle #647481, link #015B82
 */
export const PageCitationItem: React.FC<PageCitationItemProps> = ({ pageLabel, citationCount, onViewInPage }) => {
    return (
        <div className="flex items-center justify-between py-2.5">
            <div className="flex items-center gap-2">
                <span className="dark:text-foreground text-sm font-medium text-[#273749]">{pageLabel}</span>
                <span className="dark:text-muted-foreground text-sm text-[#647481]">
                    {citationCount} citation{citationCount !== 1 ? "s" : ""}
                </span>
            </div>
            <button onClick={onViewInPage} disabled={!onViewInPage} className="dark:text-primary text-sm text-[#015B82] hover:underline disabled:cursor-not-allowed disabled:opacity-50">
                View in Page
            </button>
        </div>
    );
};
