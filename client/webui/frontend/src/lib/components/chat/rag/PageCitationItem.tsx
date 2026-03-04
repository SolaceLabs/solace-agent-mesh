import React from "react";

export interface PageCitationItemProps {
    pageLabel: string;
    citationCount: number;
}

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
