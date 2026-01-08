import { useEffect, useMemo } from "react";
import type { BaseRendererProps } from ".";

// CSV parser that handles quoted fields with commas and line breaks
const parseCsv = (csvString: string): string[][] => {
    if (!csvString) return [];

    const rows: string[][] = [];
    let currentRow: string[] = [];
    let currentField = "";
    let inQuotes = false;

    // Process character by character
    for (let i = 0; i < csvString.length; i++) {
        const char = csvString[i];
        const nextChar = i < csvString.length - 1 ? csvString[i + 1] : "";

        // Handle quotes
        if (char === '"') {
            // Check for escaped quotes (double quotes)
            if (nextChar === '"') {
                currentField += '"';
                i++; // Skip the next quote
            } else {
                // Toggle quote state
                inQuotes = !inQuotes;
            }
        }
        // Handle commas
        else if (char === "," && !inQuotes) {
            // End of field
            currentRow.push(currentField.trim());
            currentField = "";
        }
        // Handle newlines
        else if ((char === "\n" || (char === "\r" && nextChar === "\n")) && !inQuotes) {
            // End of field and row
            if (char === "\r" && nextChar === "\n") {
                i++; // Skip the next \n
            }

            // Add the last field to the current row
            currentRow.push(currentField.trim());
            currentField = "";

            // Add the row if it's not empty
            if (currentRow.some(field => field.trim())) {
                rows.push(currentRow);
                currentRow = [];
            } else {
                currentRow = [];
            }
        }
        // All other characters
        else {
            currentField += char;
        }
    }

    // Add the last field and row if there's any
    if (currentField || currentRow.length > 0) {
        currentRow.push(currentField.trim());
        if (currentRow.some(field => field.trim())) {
            rows.push(currentRow);
        }
    }

    return rows;
};

export const CsvRenderer: React.FC<BaseRendererProps> = ({ content, setRenderError }) => {
    useEffect(() => {
        setRenderError(null);
    }, [content, setRenderError]);

    const rows = useMemo(() => {
        try {
            return parseCsv(content);
        } catch (e) {
            console.error("Error parsing CSV:", e);
            setRenderError("Failed to parse CSV content.");
            return [];
        }
    }, [content, setRenderError]);

    if (!rows.length) {
        return <div>No valid CSV content found or failed to parse.</div>;
    }

    return (
        <div className="block w-full overflow-x-scroll p-4">
            <div style={{ minWidth: "min(100%, max-content)" }}>
                <table className="w-full border text-sm">
                    <thead className="sticky top-0 z-10 shadow-sm">
                        {rows.length > 0 && (
                            <tr>
                                {rows[0].map((header, i) => (
                                    <th key={`header-${i}`} className="border-b p-2 text-left font-medium whitespace-nowrap" title={header}>
                                        {header?.trim() || ""}
                                    </th>
                                ))}
                            </tr>
                        )}
                    </thead>
                    <tbody>
                        {rows.slice(1).map((row, i) => (
                            <tr key={`row-${i}`} className={i % 2 === 0 ? "bg-muted dark:bg-gray-700" : ""}>
                                {row.map((cell, j) => (
                                    <td key={`cell-${i}-${j}`} className="min-w-0 border-b p-2 align-top break-words" title={cell}>
                                        {cell?.trim() || ""}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
