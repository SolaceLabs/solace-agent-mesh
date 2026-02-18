import React from "react";

import { Button } from "@/lib/components/ui/button";

export interface PageCitationItemProps {
    pageLabel: string;
    citationCount: number;
    onViewInPage?: () => void;
}

/**
 * Individual page row within a document card
 * Displays page label, citation count, and optional "View in Page" button
 * Colors from Figma: title #273749, subtitle #647481
 */
export const PageCitationItem: React.FC<PageCitationItemProps> = ({ pageLabel, citationCount, onViewInPage }) => {
    return (
        <div className="flex items-center justify-between py-2.5">
            <div className="flex items-center gap-2">
                <span className="dark:text-foreground min-w-[60px] text-sm font-semibold">{pageLabel}</span>
                <span className="dark:text-muted-foreground text-sm">
                    {citationCount} citation{citationCount !== 1 ? "s" : ""}
                </span>
            </div>
            {onViewInPage && (
                <Button variant="link" className="h-auto p-0 text-sm" onClick={onViewInPage}>
                    View in Page
                </Button>
            )}
        </div>
    );
};
