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
    const edgeStyle = { strokeWidth: 2, stroke: "var(--secondary-w70)" };

    // Straight line for condition pill → target edges
    if (data?.isStraight) {
        const path = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
        return (
            <BaseEdge
                id={id}
                path={path}
                style={edgeStyle}
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
            style={edgeStyle}
            markerEnd={markerEnd}
        />
    );
};

export const WorkflowDiagramEdge = memo(WorkflowDiagramEdgeComponent);
