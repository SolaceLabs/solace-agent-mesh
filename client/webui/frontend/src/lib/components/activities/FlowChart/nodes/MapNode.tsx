import { Fragment, useMemo, type FC } from "react";
import { Repeat2 } from "lucide-react";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, CONNECTOR_LINE_CLASSES, CONNECTOR_SIZES } from "../utils/nodeStyles";
import AgentNode from "./AgentNode";

interface MapNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
    onChildClick?: (child: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
}

const MapNode: FC<MapNodeProps> = ({ node, isSelected, onClick, onChildClick, onExpand, onCollapse }) => {
    // Layout constants
    const HEADER_HEIGHT = 44;

    // Group children by iterationIndex to create branches
    const branches = useMemo(() => {
        const branchMap = new Map<number, typeof node.children>();
        for (const child of node.children) {
            const iterationIndex = child.data.iterationIndex ?? 0;
            if (!branchMap.has(iterationIndex)) {
                branchMap.set(iterationIndex, []);
            }
            branchMap.get(iterationIndex)!.push(child);
        }
        // Sort by iteration index and return as array of arrays
        return Array.from(branchMap.entries())
            .sort((a, b) => a[0] - b[0])
            .map(([, children]) => children);
    }, [node]);

    const hasChildren = branches.length > 0;
    const label = "Map";

    // Render a child node (iterations are agent nodes)
    const renderChild = (child: LayoutNode) => {
        const childProps = {
            node: child,
            onClick: onChildClick,
            onChildClick: onChildClick,
            onExpand,
            onCollapse,
        };

        switch (child.type) {
            case "agent":
                return <AgentNode key={child.id} {...childProps} />;
            default:
                return null;
        }
    };

    // If the node has children, render as expanded container with dotted border
    if (hasChildren) {
        return (
            <div className="flex flex-col px-4" style={{ width: 'fit-content', minWidth: '200px' }}>
                {/* Solid Header Box - positioned at top */}
                <div
                    className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
                    onClick={e => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    <div className="flex items-center gap-2 px-4 py-2">
                        <Repeat2 className="h-4 w-4 text-(--color-accent-n0-wMain)" />
                        <span className="text-sm font-semibold">{node.data.label || label}</span>
                    </div>
                </div>

                {/* Dotted Children Container - grows with content */}
                <div
                    className="rounded border-1 border-dashed border-(--color-secondary-w40) bg-(--color-secondary-w10) dark:border-(--color-secondary-w70) dark:bg-(--color-secondary-w100)"
                    style={{ marginTop: `-${HEADER_HEIGHT / 2}px`, paddingTop: `${HEADER_HEIGHT / 2 + 16}px` }}
                >
                    <div className="px-3 pb-4">
                        {/* Parallel branches displayed side-by-side */}
                        <div className="grid gap-4" style={{ gridAutoFlow: "column", gridAutoColumns: "1fr" }}>
                            {branches.map((branch, branchIndex) => (
                                <div key={`branch-${branchIndex}`} className="flex flex-col items-center">
                                    {branch.map((child, childIndex) => (
                                        <Fragment key={child.id}>
                                            {renderChild(child)}
                                            {/* Connector line to next child in same branch */}
                                            {childIndex < branch.length - 1 && <div className={`my-1 ${CONNECTOR_SIZES.MAIN} ${CONNECTOR_LINE_CLASSES}`} />}
                                        </Fragment>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    // No children - render as compact node
    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""}`}
            style={{ width: 'fit-content', minWidth: '120px' }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2">
                <Repeat2 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <span className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">{node.data.label || label}</span>
            </div>
        </div>
    );
};

export default MapNode;
