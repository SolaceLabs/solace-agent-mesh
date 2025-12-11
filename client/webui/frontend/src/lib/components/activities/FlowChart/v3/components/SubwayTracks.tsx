import React, { useState } from "react";
import type { TrackSegment, BranchPoint } from "../utils/types";

interface SubwayTracksProps {
    tracks: TrackSegment[];
    branches: BranchPoint[];
    laneXPositions: number[]; // X position for each lane
    selectedTrackId?: string | null;
    onTrackClick?: (track: TrackSegment) => void;
}

const SubwayTracks: React.FC<SubwayTracksProps> = ({
    tracks,
    branches,
    laneXPositions,
    selectedTrackId,
    onTrackClick,
}) => {
    const [hoveredTrackId, setHoveredTrackId] = useState<string | null>(null);

    // Calculate path for a track segment
    const getTrackPath = (track: TrackSegment): string => {
        const fromX = laneXPositions[track.fromLane] || 0;
        const toX = laneXPositions[track.toLane] || 0;
        const fromY = track.fromY;
        const toY = track.toY;

        if (track.fromLane === track.toLane) {
            // Straight vertical line
            return `M ${fromX} ${fromY} L ${toX} ${toY}`;
        } else {
            // Curved transition between lanes
            const midY = (fromY + toY) / 2;
            return `M ${fromX} ${fromY} L ${fromX} ${midY} L ${toX} ${midY} L ${toX} ${toY}`;
        }
    };

    // Get track style
    const getTrackStyle = (track: TrackSegment, isHovered: boolean) => {
        const isSelected = track.id === selectedTrackId;

        return {
            stroke: track.color,
            strokeWidth: isSelected ? 4 : isHovered ? 3 : 2.5,
            strokeDasharray: track.style === 'dashed' ? '5,5' : 'none',
            opacity: track.style === 'dashed' ? 0.5 : 1,
        };
    };

    // Render branch/join points
    const renderBranch = (branch: BranchPoint) => {
        const sourceX = laneXPositions[branch.sourceLane] || 0;

        if (branch.type === 'fork') {
            // Draw curves from source to each target lane
            return branch.targetLanes.map(targetLane => {
                const targetX = laneXPositions[targetLane] || 0;
                const midY = branch.y + 20;

                // Bezier curve for smooth branch
                const path = `M ${sourceX} ${branch.y} Q ${sourceX} ${midY}, ${(sourceX + targetX) / 2} ${midY} T ${targetX} ${midY + 20}`;

                return (
                    <path
                        key={`fork_${branch.id}_${targetLane}`}
                        d={path}
                        fill="none"
                        stroke={branch.color}
                        strokeWidth={2.5}
                        opacity={0.8}
                    />
                );
            });
        } else {
            // Join - curves from source back to target
            return branch.targetLanes.map(targetLane => {
                const targetX = laneXPositions[targetLane] || 0;
                const midY = branch.y - 20;

                const path = `M ${sourceX} ${branch.y - 40} Q ${sourceX} ${midY}, ${(sourceX + targetX) / 2} ${midY} T ${targetX} ${branch.y}`;

                return (
                    <path
                        key={`join_${branch.id}_${targetLane}`}
                        d={path}
                        fill="none"
                        stroke={branch.color}
                        strokeWidth={2.5}
                        opacity={0.8}
                    />
                );
            });
        }
    };

    return (
        <g>
            {/* Render all tracks */}
            {tracks.map(track => {
                const isHovered = track.id === hoveredTrackId;
                const path = getTrackPath(track);
                const style = getTrackStyle(track, isHovered);

                return (
                    <g key={track.id}>
                        {/* Invisible wider path for easier clicking */}
                        <path
                            d={path}
                            fill="none"
                            stroke="transparent"
                            strokeWidth="16"
                            style={{ cursor: 'pointer' }}
                            onMouseEnter={() => setHoveredTrackId(track.id)}
                            onMouseLeave={() => setHoveredTrackId(null)}
                            onClick={() => onTrackClick?.(track)}
                        />

                        {/* Visible track */}
                        <path
                            d={path}
                            fill="none"
                            {...style}
                            style={{
                                transition: 'all 0.2s ease-in-out',
                            }}
                        />
                    </g>
                );
            })}

            {/* Render branch/join points */}
            {branches.map(renderBranch)}
        </g>
    );
};

export default SubwayTracks;
