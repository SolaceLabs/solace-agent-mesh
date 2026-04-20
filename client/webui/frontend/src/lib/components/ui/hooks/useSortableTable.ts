import { useState } from "react";

type SortDir = "asc" | "desc";

export function useSortableTable<T extends object>(data: T[], columns: (keyof T & string)[]) {
    const [sortKey, setSortKey] = useState<keyof T & string>(columns[0]);
    const [sortDir, setSortDir] = useState<SortDir>("asc");

    const handleSort = (column: string) => {
        const key = column as keyof T & string;
        if (sortKey === key) {
            setSortDir(d => (d === "asc" ? "desc" : "asc"));
        } else {
            setSortKey(key);
            setSortDir("asc");
        }
    };

    const toStr = (val: unknown): string => (typeof val === "string" || typeof val === "number" || typeof val === "boolean" ? String(val) : "").toLowerCase();

    const sortedData = [...data].sort((a, b) => {
        const aVal = toStr((a as Record<string, unknown>)[sortKey]);
        const bVal = toStr((b as Record<string, unknown>)[sortKey]);
        const cmp = aVal.localeCompare(bVal);
        return sortDir === "asc" ? cmp : -cmp;
    });

    return { sortedData, sortKey, sortDir, handleSort };
}
