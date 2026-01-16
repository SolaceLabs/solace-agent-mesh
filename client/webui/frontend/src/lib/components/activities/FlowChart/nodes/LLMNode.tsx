import type { FC } from "react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import type { LayoutNode } from "../utils/types";

interface LLMNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const LLMNode: FC<LLMNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? 'processing-halo' : '';

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <div
                    className={`relative overflow-hidden cursor-pointer rounded-full border-2 border-(--color-accent-n2-wMain) bg-(--color-background-w10) px-3 py-1 text-(--color-primary-text-wMain) shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-(--color-accent-n2-w30) dark:bg-(--color-background-wMain) dark:text-(--color-primary-text-w10) ${
                        isSelected ? "ring-2 ring-blue-500" : ""
                    } ${haloClass}`}
                    style={{
                        textAlign: "center",
                    }}
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    <div className="text-sm">
                        {node.data.label}
                    </div>
                </div>
            </TooltipTrigger>
            {node.data.description && (
                <TooltipContent>{node.data.description}</TooltipContent>
            )}
        </Tooltip>
    );
};

export default LLMNode;
