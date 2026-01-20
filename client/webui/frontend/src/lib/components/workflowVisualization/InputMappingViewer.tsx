import React, { useCallback } from "react";
import { Search } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { getValidNodeReferences } from "./utils/expressionParser";

interface InputMappingViewerProps {
    /** The input mapping object (key-value pairs where values may contain expressions) */
    mapping: Record<string, unknown>;
    /** Callback to highlight nodes when hovering over expressions */
    onHighlightNodes?: (nodeIds: string[]) => void;
    /** Set of known node IDs for validating expression references */
    knownNodeIds?: Set<string>;
    /** Callback to navigate/pan to a node when clicking the navigation icon */
    onNavigateToNode?: (nodeId: string) => void;
}

/**
 * Renders a single value from the input mapping, with hover highlighting for expressions
 */
const MappingValue: React.FC<{
    value: unknown;
    onHighlightNodes?: (nodeIds: string[]) => void;
    knownNodeIds?: Set<string>;
    onNavigateToNode?: (nodeId: string) => void;
    depth?: number;
}> = ({ value, onHighlightNodes, knownNodeIds, onNavigateToNode, depth = 0 }) => {
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
        const nodeRefs = hasExprs ? getNodeRefs(value) : [];
        const hasNodeRefs = nodeRefs.length > 0;

        // Handle navigation to the first referenced node
        const handleNavigate = (e: React.MouseEvent) => {
            e.stopPropagation();
            if (hasNodeRefs && onNavigateToNode) {
                onNavigateToNode(nodeRefs[0]);
            }
        };

        return (
            <span className="inline-flex items-end gap-1">
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
                {hasNodeRefs && onNavigateToNode && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleNavigate}
                        onMouseEnter={() => onHighlightNodes?.([nodeRefs[0]])}
                        onMouseLeave={() => onHighlightNodes?.([])}
                        tooltip={`Navigate to ${nodeRefs[0]}`}
                    >
                        <Search className="h-6 w-6" />
                    </Button>
                )}
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
                            onNavigateToNode={onNavigateToNode}
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
                            onNavigateToNode={onNavigateToNode}
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
    onNavigateToNode,
}) => {
    const entries = Object.entries(mapping);

    if (entries.length === 0) {
        return (
            <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-center text-sm">
                No input mapping defined
            </div>
        );
    }

    // Helper to check if value has node references
    const getNodeRefsForValue = (value: unknown): string[] => {
        if (typeof value === "string" && knownNodeIds) {
            return getValidNodeReferences(value, knownNodeIds);
        }
        return [];
    };

    return (
        <div className="space-y-4">
            {entries.map(([key, value]) => {
                const nodeRefs = getNodeRefsForValue(value);
                const hasNodeRefs = nodeRefs.length > 0;

                return (
                    <div key={key} className="space-y-1">
                        <div className="font-mono text-sm text-[var(--color-primary-text-wMain)]">{key}</div>
                        <div className="flex items-start gap-2">
                            <div className="min-h-[27px] flex-1 break-words overflow-auto bg-[var(--color-background-w20)] px-2.5 py-1">
                                <MappingValue
                                    value={value}
                                    onHighlightNodes={onHighlightNodes}
                                    knownNodeIds={knownNodeIds}
                                    onNavigateToNode={undefined}
                                />
                            </div>
                            {hasNodeRefs && onNavigateToNode && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => onNavigateToNode(nodeRefs[0])}
                                    onMouseEnter={() => onHighlightNodes?.([nodeRefs[0]])}
                                    onMouseLeave={() => onHighlightNodes?.([])}
                                    tooltip={`Navigate to ${nodeRefs[0]}`}
                                    className="h-6 w-6 opacity-50 hover:opacity-100"
                                >
                                    <Search className="h-6 w-6" />
                                </Button>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

export default InputMappingViewer;
