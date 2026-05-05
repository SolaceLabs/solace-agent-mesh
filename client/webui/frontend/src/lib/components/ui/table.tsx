import * as React from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "./button";

type SortDir = "asc" | "desc";

interface SortableTableHeadProps extends React.ComponentProps<"th"> {
    column: string;
    currentSortKey: string;
    sortDir: SortDir;
    onSort: (column: string) => void;
}

function SortableTableHead({ column, currentSortKey, sortDir, onSort, children, className, ...props }: SortableTableHeadProps) {
    const isActive = currentSortKey === column;
    return (
        <TableHead className={cn("font-semibold", className)} {...props}>
            <Button variant="ghost" size="icon" className="h-auto w-auto gap-1 px-1.5 py-0.5 text-(--primary-text-wMain)" onClick={() => onSort(column)}>
                {children}
                {isActive ? sortDir === "asc" ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" /> : <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />}
            </Button>
        </TableHead>
    );
}

function Table({ className, ...props }: React.ComponentProps<"table">) {
    return (
        <div data-slot="table-container" className="relative w-full overflow-x-auto">
            <table data-slot="table" className={cn("w-full caption-bottom text-sm", className)} {...props} />
        </div>
    );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
    return <thead data-slot="table-header" className={cn("[&_tr]:border-b", className)} {...props} />;
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
    return <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
    return <tfoot data-slot="table-footer" className={cn("border-t bg-(--secondary-w10) font-medium [&>tr]:last:border-b-0", className)} {...props} />;
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
    return <tr data-slot="table-row" className={cn("border-b transition-colors hover:bg-(--primary-w10) data-[state=selected]:bg-(--secondary-w10)", className)} {...props} />;
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
    return <th data-slot="table-head" className={cn("h-10 px-2 text-left align-middle font-medium whitespace-nowrap text-(--primary-text-wMain) [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]", className)} {...props} />;
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
    return <td data-slot="table-cell" className={cn("p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]", className)} {...props} />;
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
    return <caption data-slot="table-caption" className={cn("mt-4 text-sm text-(--secondary-text-wMain)", className)} {...props} />;
}

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption, SortableTableHead };
