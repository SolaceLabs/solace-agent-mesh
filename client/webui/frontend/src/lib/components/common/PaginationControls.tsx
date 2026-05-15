import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/lib/components/ui/pagination";
import { paginationPages } from "@/lib/utils/pagination";
import { cn } from "@/lib/utils";

interface PaginationControlsProps {
    totalPages: number;
    currentPage: number;
    onPageChange: (page: number) => void;
    /**
     * "default" renders the standard prev/next labels inside a bordered footer
     * suitable for a full-width page footer. "compact" renders chevron-only
     * prev/next and drops the surrounding chrome — use it under a results
     * table when the page already provides the container.
     */
    variant?: "default" | "compact";
    /**
     * Optional summary text rendered absolute-right relative to the centered
     * pagination strip (e.g. "Showing 11-20 of 87 results"). Only used by the
     * compact variant.
     */
    summary?: React.ReactNode;
    className?: string;
}

export const PaginationControls: React.FC<PaginationControlsProps> = ({ totalPages, currentPage, onPageChange, variant = "default", summary, className }) => {
    if (totalPages <= 1) return null;

    if (variant === "compact") {
        const prevDisabled = currentPage <= 1;
        const nextDisabled = currentPage >= totalPages;
        return (
            <div className={cn("relative mt-3 flex items-center justify-center", className)}>
                <Pagination>
                    <PaginationContent>
                        <PaginationItem>
                            <PaginationLink aria-label="Go to previous page" onClick={() => !prevDisabled && onPageChange(currentPage - 1)} className={prevDisabled ? "pointer-events-none opacity-50" : "cursor-pointer"}>
                                <ChevronLeft className="h-4 w-4" />
                            </PaginationLink>
                        </PaginationItem>
                        {paginationPages(currentPage, totalPages).map((page, index) => (
                            <PaginationItem key={index}>
                                {page === "ellipsis" ? (
                                    <PaginationEllipsis />
                                ) : (
                                    <PaginationLink isActive={currentPage === page} onClick={() => onPageChange(page as number)} className="cursor-pointer">
                                        {page}
                                    </PaginationLink>
                                )}
                            </PaginationItem>
                        ))}
                        <PaginationItem>
                            <PaginationLink aria-label="Go to next page" onClick={() => !nextDisabled && onPageChange(currentPage + 1)} className={nextDisabled ? "pointer-events-none opacity-50" : "cursor-pointer"}>
                                <ChevronRight className="h-4 w-4" />
                            </PaginationLink>
                        </PaginationItem>
                    </PaginationContent>
                </Pagination>
                {summary && <span className="absolute top-1/2 right-2 -translate-y-1/2 text-xs text-(--secondary-text-wMain)">{summary}</span>}
            </div>
        );
    }

    return (
        <div className={cn("mt-4 flex flex-shrink-0 justify-center border-t bg-(--background-w10) pt-4 pb-2", className)}>
            <Pagination>
                <PaginationContent>
                    <PaginationItem>
                        <PaginationPrevious onClick={() => onPageChange(currentPage - 1)} className={currentPage === 1 ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                    </PaginationItem>

                    {paginationPages(currentPage, totalPages).map((page, index) => (
                        <PaginationItem key={index}>
                            {page === "ellipsis" ? (
                                <PaginationEllipsis />
                            ) : (
                                <PaginationLink onClick={() => onPageChange(page as number)} isActive={currentPage === page} className="cursor-pointer">
                                    {page}
                                </PaginationLink>
                            )}
                        </PaginationItem>
                    ))}

                    <PaginationItem>
                        <PaginationNext onClick={() => onPageChange(currentPage + 1)} className={currentPage === totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"} />
                    </PaginationItem>
                </PaginationContent>
            </Pagination>
        </div>
    );
};
