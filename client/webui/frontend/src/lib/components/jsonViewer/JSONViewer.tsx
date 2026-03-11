import React, { useMemo } from "react";

import { JsonEditor, type Theme as JerTheme } from "json-edit-react";

const jsonEditorTheme: JerTheme = {
    displayName: "Solace JER",
    styles: {
        container: {
            backgroundColor: "transparent",
            fontFamily: "monospace",
            fontSize: "14px",
        },
        property: "var(--primary-text-wMain)",
        bracket: "var(--secondary-text-w50)",
        itemCount: { color: "var(--secondary-text-w50)", fontStyle: "italic" },
        string: "var(--error-w100)",
        number: "var(--brand-w100)",
        boolean: "var(--info-wMain)",
        null: { color: "var(--secondary-text-w50)", fontStyle: "italic" },
        iconCollection: "var(--secondary-text-w50)",
        iconCopy: "var(--secondary-text-w50)",
    },
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
