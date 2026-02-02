import React, { useMemo } from "react";

import { JsonEditor, type Theme as JerTheme } from "json-edit-react";

import { useThemeContext } from "@/lib/hooks/useThemeContext";

/**
 * Creates a theme object for JsonEditor that uses the application's CSS variables.
 * This ensures the JSON viewer's appearance is consistent with the current theme.
 * @param isDark - Whether the current theme is a dark theme.
 * @returns A theme object compatible with `json-edit-react`.
 */
const createJsonEditorTheme = (isDark: boolean): JerTheme => {
    return {
        displayName: isDark ? "Solace Dark JER" : "Solace Light JER",
        styles: {
            container: {
                backgroundColor: "transparent",
                fontFamily: "monospace",
                fontSize: "14px",
            },
            property: isDark ? "var(--color-primary-text-w10)" : "var(--color-primary-text-wMain)",
            bracket: "var(--color-secondary-text-w50)",
            itemCount: { color: "var(--color-secondary-text-w50)", fontStyle: "italic" },
            string: "var(--color-error-w100)",
            number: "var(--color-brand-w100)",
            boolean: isDark ? "var(--color-info-w70)" : "var(--color-info-wMain)",
            null: { color: "var(--color-secondary-text-w50)", fontStyle: "italic" },
            // In view-only mode, we only need the collection and copy icons.
            iconCollection: "var(--color-secondary-text-w50)",
            iconCopy: "var(--color-secondary-text-w50)",
        },
    };
};

export type JSONValue = string | number | boolean | null | JSONObject | JSONArray;
type JSONObject = { [key: string]: JSONValue };
type JSONArray = JSONValue[];

interface JSONViewerProps {
    data: JSONValue;
    maxDepth?: number;
    className?: string;
    /** Root name label. Set to empty string to hide. Defaults to empty (hidden). */
    rootName?: string;
}

export const JSONViewer: React.FC<JSONViewerProps> = ({ data, maxDepth = 2, className = "", rootName = "" }) => {
    const { currentTheme } = useThemeContext();

    const jsonEditorTheme = useMemo(() => {
        return createJsonEditorTheme(currentTheme === "dark");
    }, [currentTheme]);

    // Determine expansion behavior based on maxDepth
    const collapseProp = useMemo(() => {
        if (maxDepth === undefined || maxDepth < 0) {
            return false;
        }
        return maxDepth;
    }, [maxDepth]);

    // Handle primitive values and null by wrapping them in an object
    const processedData = useMemo(() => {
        if (data === null || typeof data !== "object") {
            return { value: data };
        }
        return data;
    }, [data]);

    const containerClasses = `rounded-lg border overflow-auto ${className}`.trim();

    if (data === undefined) {
        return (
            <div className={containerClasses}>
                <span className="italic">No JSON data</span>
            </div>
        );
    }

    return (
        <div className={containerClasses}>
            <JsonEditor data={processedData as object | unknown[]} theme={jsonEditorTheme} viewOnly={true} collapse={collapseProp} showStringQuotes={true} showCollectionCount="when-closed" rootName={rootName} />
        </div>
    );
};
