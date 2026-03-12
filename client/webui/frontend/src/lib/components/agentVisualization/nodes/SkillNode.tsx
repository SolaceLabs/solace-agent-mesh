import type { FC } from "react";
import { Sparkles } from "lucide-react";
import { NODE_BASE_STYLES, NODE_SELECTED_CLASS } from "../../workflowVisualization/utils/types";
import type { AgentNodeProps } from "../utils/types";

/**
 * SkillNode - Represents a skill in the agent diagram.
 * Shows the skill name with a sparkles icon.
 */
const SkillNode: FC<AgentNodeProps> = ({ node, isSelected, onClick }) => {
    const name = node.data.skillName || node.data.label;

    return (
        <div
            className={`${NODE_BASE_STYLES.RECTANGULAR} ${isSelected ? NODE_SELECTED_CLASS : ""}`}
            style={{
                width: `${node.width}px`,
                height: `${node.height}px`,
            }}
            onClick={e => {
                e.stopPropagation();
                onClick?.(node);
            }}
        >
            <div className="flex items-center gap-2 overflow-hidden">
                <Sparkles className="h-4 w-4 flex-shrink-0 text-(--color-info-wMain)" />
                <span className="truncate text-sm">{name}</span>
            </div>
            <span className="text-secondary-foreground ml-2 flex-shrink-0 rounded px-1.5 py-0.5 text-xs">Skill</span>
        </div>
    );
};

export default SkillNode;
