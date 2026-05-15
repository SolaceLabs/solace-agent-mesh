/**
 * Build the list of page numbers (with "ellipsis" placeholders) shown in a
 * pagination control. Mirrors the layout used by `common/PaginationControls`:
 * when there are more than 5 pages, collapse the middle with ellipses and
 * always include first/last.
 */
export const paginationPages = (currentPage: number, totalPages: number): (number | "ellipsis")[] => {
    const pages: (number | "ellipsis")[] = [];
    if (totalPages <= 5) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
        return pages;
    }
    if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i);
        pages.push("ellipsis", totalPages);
    } else if (currentPage >= totalPages - 2) {
        pages.push(1, "ellipsis");
        for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
    } else {
        pages.push(1, "ellipsis");
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i);
        pages.push("ellipsis", totalPages);
    }
    return pages;
};
