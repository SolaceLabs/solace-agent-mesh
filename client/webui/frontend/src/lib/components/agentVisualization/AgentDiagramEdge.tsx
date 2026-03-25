import { memo } from "react";
import { BaseEdge, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

const AgentDiagramEdgeComponent: React.FC<EdgeProps> = ({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, markerEnd }) => {
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

    return <BaseEdge id={id} path={edgePath} style={{ strokeWidth: 2, stroke: "var(--secondary-w70)" }} markerEnd={markerEnd} />;
};

export const AgentDiagramEdge = memo(AgentDiagramEdgeComponent);
