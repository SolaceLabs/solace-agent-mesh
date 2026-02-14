import type { FC } from "react";
import { FileText, Wrench } from "lucide-react";

import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";

import type { LayoutNode } from "../utils/types";
import { ACTIVITY_NODE_BASE_STYLES, ACTIVITY_NODE_SELECTED_CLASS, ACTIVITY_NODE_PROCESSING_CLASS } from "../utils/nodeStyles";

interface ToolNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ToolNode: FC<ToolNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? ACTIVITY_NODE_PROCESSING_CLASS : "";
    const artifactCount = node.data.createdArtifacts?.length || 0;

    return (
        <div
            className={`${ACTIVITY_NODE_BASE_STYLES.RECTANGULAR_COMPACT} ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
            style={{ width: 'fit-content', minWidth: '120px' }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2">
                <Wrench className="h-4 w-4 flex-shrink-0 text-cyan-600 dark:text-cyan-400" />
                <div className="truncate text-sm font-semibold">{node.data.label}</div>
                {artifactCount > 0 && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <span className="flex items-center gap-0.5 rounded-full bg-indigo-100 px-1 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300">
                                <FileText className="h-2.5 w-2.5" />
                                {artifactCount}
                            </span>
                        </TooltipTrigger>
                        <TooltipContent>{`${artifactCount} ${artifactCount === 1 ? "artifact" : "artifacts"} created`}</TooltipContent>
                    </Tooltip>
                )}
            </div>
        </div>
    );
};

export default ToolNode;
