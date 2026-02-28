import type { FC } from "react";
import { Wrench } from "lucide-react";

import { Badge } from "@/lib/components/ui";
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
            className={`${ACTIVITY_NODE_BASE_STYLES.CONTAINER_HEADER} flex flex-col justify-center ${isSelected ? ACTIVITY_NODE_SELECTED_CLASS : ""} ${haloClass}`}
            style={{ width: "225px", minHeight: "50px" }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2 px-4 py-2">
                <Wrench className="h-4 w-4 flex-shrink-0 text-(--color-accent-n7-wMain) dark:text-(--color-accent-n7-w100)" />
                <div className="truncate text-sm font-semibold">{node.data.label}</div>
            </div>
            {artifactCount > 0 && (
                <div className="px-4 pt-0 pb-2 pl-10">
                    <Badge variant="default">
                        {artifactCount} {artifactCount === 1 ? "artifact" : "artifacts"}
                    </Badge>
                </div>
            )}
        </div>
    );
};

export default ToolNode;
