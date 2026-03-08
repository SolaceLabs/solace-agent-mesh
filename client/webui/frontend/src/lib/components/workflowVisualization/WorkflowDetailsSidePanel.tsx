import type { AgentCardInfo } from "@/lib/types";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import { WorkflowDetailPanel } from "@/lib/components/workflows/WorkflowDetailPanel";

export type WorkflowPanelView = "details" | "code";

interface WorkflowDetailsSidePanelProps {
    workflow: AgentCardInfo | null;
    config: WorkflowConfig | null;
    view: WorkflowPanelView;
    onClose: () => void;
    onViewChange: (view: WorkflowPanelView) => void;
}

/**
 * Side panel for showing workflow-level details on the workflow diagram page.
 * Wraps WorkflowDetailPanel with diagram-specific props.
 */
const WorkflowDetailsSidePanel = ({ workflow, config, view: _view, onClose, onViewChange: _onViewChange }: WorkflowDetailsSidePanelProps) => {
    // The view and onViewChange props are kept for backwards compatibility
    // but the WorkflowDetailPanel now manages its own view state internally
    void _view;
    void _onViewChange;

    if (!workflow || !config) {
        return null;
    }

    return <WorkflowDetailPanel workflow={workflow} config={config} onClose={onClose} showOpenButton={false} />;
};

export default WorkflowDetailsSidePanel;
