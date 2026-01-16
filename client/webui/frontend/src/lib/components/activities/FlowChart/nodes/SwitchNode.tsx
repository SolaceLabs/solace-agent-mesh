import type { FC } from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import type { LayoutNode } from "../utils/types";

interface SwitchNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const SwitchNode: FC<SwitchNodeProps> = ({ node, isSelected, onClick }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-purple-100 border-purple-500 dark:bg-purple-900/30 dark:border-purple-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    const casesCount = node.data.cases?.length || 0;
    const hasDefault = !!node.data.defaultBranch;

    // Build tooltip with selected branch info
    const baseTooltip = node.data.description || `Switch with ${casesCount} case${casesCount !== 1 ? 's' : ''}${hasDefault ? ' + default' : ''}`;
    const tooltip = node.data.selectedBranch
        ? `${baseTooltip}\nSelected: ${node.data.selectedBranch}`
        : baseTooltip;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <div
                    className="group/switch relative flex items-center justify-center cursor-pointer"
                    style={{ width: `${node.width}px`, height: `${node.height}px` }}
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    {/* Diamond Shape using rotation - same as conditional */}
                    <div
                        className={`absolute h-12 w-12 rotate-45 border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md ${getStatusColor()} ${
                            isSelected ? "ring-2 ring-blue-500" : ""
                        }`}
                    />

                    {/* Content (unrotated) */}
                    <div className="z-10 flex flex-col items-center justify-center text-center pointer-events-none px-1">
                        <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200 max-w-[100px] truncate">
                            {/* Show selected branch when completed, otherwise show label */}
                            {node.data.selectedBranch || node.data.label}
                        </div>
                        {/* Show case count only when not yet completed */}
                        {!node.data.selectedBranch && (
                            <div className="text-[8px] text-gray-500 dark:text-gray-400">
                                {casesCount} case{casesCount !== 1 ? 's' : ''}
                            </div>
                        )}
                    </div>
                </div>
            </TooltipTrigger>
            <TooltipContent>{tooltip}</TooltipContent>
        </Tooltip>
    );
};

export default SwitchNode;
