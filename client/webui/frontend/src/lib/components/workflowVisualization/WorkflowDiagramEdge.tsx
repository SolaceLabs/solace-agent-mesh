import { memo } from "react";
import { BaseEdge, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

const WorkflowDiagramEdgeComponent: React.FC<EdgeProps> = ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    markerEnd,
    data,
}) => {
    // Straight line for condition pill → target edges
    if (data?.isStraight) {
        const path = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
        return (
            <BaseEdge
                id={id}
                path={path}
                style={{ strokeWidth: 2 }}
                className="stroke-(--color-secondary-w70) dark:stroke-(--color-secondary-w70)"
                markerEnd={markerEnd}
            />
        );
    }

    const [edgePath] = getSmoothStepPath({
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourcePosition,
        targetPosition,
        borderRadius: 16,
        offset: 24,
    });

    return (
        <BaseEdge
            id={id}
            path={edgePath}
            style={{ strokeWidth: 2 }}
            className="stroke-(--color-secondary-w70) dark:stroke-(--color-secondary-w70)"
            markerEnd={markerEnd}
        />
    );
};

export const WorkflowDiagramEdge = memo(WorkflowDiagramEdgeComponent);
