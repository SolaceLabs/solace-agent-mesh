import React, { useCallback } from "react";
import { getValidNodeReferences } from "./utils/expressionParser";

interface InputMappingViewerProps {
    /** The input mapping object (key-value pairs where values may contain expressions) */
    mapping: Record<string, unknown>;
    /** Callback to highlight nodes when hovering over expressions */
    onHighlightNodes?: (nodeIds: string[]) => void;
    /** Set of known node IDs for validating expression references */
    knownNodeIds?: Set<string>;
}

/**
 * Renders a single value from the input mapping, with hover highlighting for expressions
 */
const MappingValue: React.FC<{
    value: unknown;
    onHighlightNodes?: (nodeIds: string[]) => void;
    knownNodeIds?: Set<string>;
    depth?: number;
}> = ({ value, onHighlightNodes, knownNodeIds, depth = 0 }) => {
    // Extract node references from a string value
    const getNodeRefs = useCallback(
        (str: string): string[] => {
            if (!onHighlightNodes || !knownNodeIds) return [];
            return getValidNodeReferences(str, knownNodeIds);
        },
        [onHighlightNodes, knownNodeIds]
    );

    // Check if a string contains template expressions
    const hasExpressions = (str: string): boolean => {
        return /\{\{[^}]+\}\}/.test(str);
    };

    // Handle mouse enter on a value with expressions
    const handleMouseEnter = useCallback(
        (str: string) => {
            const refs = getNodeRefs(str);
            if (refs.length > 0) {
                onHighlightNodes?.(refs);
            }
        },
        [getNodeRefs, onHighlightNodes]
    );

    // Handle mouse leave - clear highlights
    const handleMouseLeave = useCallback(() => {
        onHighlightNodes?.([]);
    }, [onHighlightNodes]);

    // Render based on value type
    if (value === null) {
        return <span className="text-gray-400 dark:text-gray-500">null</span>;
    }

    if (value === undefined) {
        return <span className="text-gray-400 dark:text-gray-500">undefined</span>;
    }

    if (typeof value === "string") {
        const hasExprs = hasExpressions(value);
        return (
            <span
                className={`font-mono text-green-700 dark:text-green-400 ${
                    hasExprs
                        ? `cursor-pointer rounded px-0.5 transition-all duration-150 hover:bg-amber-100 dark:hover:bg-amber-900/30`
                        : ""
                }`}
                onMouseEnter={hasExprs ? () => handleMouseEnter(value) : undefined}
                onMouseLeave={hasExprs ? handleMouseLeave : undefined}
                title={hasExprs ? "Hover to highlight source nodes" : undefined}
            >
                "{value}"
            </span>
        );
    }

    if (typeof value === "number") {
        return <span className="font-mono text-blue-600 dark:text-blue-400">{value}</span>;
    }

    if (typeof value === "boolean") {
        return <span className="font-mono text-purple-600 dark:text-purple-400">{value.toString()}</span>;
    }

    if (Array.isArray(value)) {
        if (value.length === 0) {
            return <span className="text-gray-500">[]</span>;
        }
        return (
            <div className="ml-3">
                <span className="text-gray-500">[</span>
                {value.map((item, index) => (
                    <div key={index} className="ml-3">
                        <MappingValue
                            value={item}
                            onHighlightNodes={onHighlightNodes}
                            knownNodeIds={knownNodeIds}
                            depth={depth + 1}
                        />
                        {index < value.length - 1 && <span className="text-gray-500">,</span>}
                    </div>
                ))}
                <span className="text-gray-500">]</span>
            </div>
        );
    }

    if (typeof value === "object") {
        const entries = Object.entries(value as Record<string, unknown>);
        if (entries.length === 0) {
            return <span className="text-gray-500">{"{}"}</span>;
        }
        return (
            <div className="ml-3">
                <span className="text-gray-500">{"{"}</span>
                {entries.map(([key, val], index) => (
                    <div key={key} className="ml-3">
                        <span className="text-gray-700 dark:text-gray-300">{key}</span>
                        <span className="text-gray-500">: </span>
                        <MappingValue
                            value={val}
                            onHighlightNodes={onHighlightNodes}
                            knownNodeIds={knownNodeIds}
                            depth={depth + 1}
                        />
                        {index < entries.length - 1 && <span className="text-gray-500">,</span>}
                    </div>
                ))}
                <span className="text-gray-500">{"}"}</span>
            </div>
        );
    }

    return <span className="text-gray-500">{String(value)}</span>;
};

/**
 * InputMappingViewer - Displays input mapping with hover highlighting for expressions
 * When hovering over a value containing template expressions like {{node_a.output.field}},
 * the referenced nodes will be highlighted in the diagram.
 */
const InputMappingViewer: React.FC<InputMappingViewerProps> = ({
    mapping,
    onHighlightNodes,
    knownNodeIds,
}) => {
    const entries = Object.entries(mapping);

    if (entries.length === 0) {
        return (
            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                No input mapping defined
            </div>
        );
    }

    return (
        <div className="rounded-lg border bg-gray-50 p-3 text-xs dark:bg-gray-900">
            {entries.map(([key, value], index) => (
                <div key={key} className={index > 0 ? "mt-1" : ""}>
                    <span className="font-medium text-gray-700 dark:text-gray-300">{key}</span>
                    <span className="text-gray-500">: </span>
                    <MappingValue
                        value={value}
                        onHighlightNodes={onHighlightNodes}
                        knownNodeIds={knownNodeIds}
                    />
                </div>
            ))}
        </div>
    );
};

export default InputMappingViewer;
