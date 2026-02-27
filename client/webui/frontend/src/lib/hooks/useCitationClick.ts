import { useCallback } from "react";
import type { Citation } from "@/lib/utils/citations";
import { useChatContext } from "./useChatContext";

/**
 * Hook to handle citation clicks - opens sources panel with the cited document
 * @param taskId - The task ID to filter sources by (optional for artifacts without taskId)
 */
export function useCitationClick(taskId?: string) {
    const { setTaskIdInSidePanel, setExpandedDocumentFilename, openSidePanelTab } = useChatContext();

    return useCallback(
        (citation: Citation) => {
            if (taskId) {
                setTaskIdInSidePanel(taskId);
                if (citation.source?.filename) {
                    setExpandedDocumentFilename(citation.source.filename);
                }
                openSidePanelTab("rag");
            }
        },
        [taskId, setTaskIdInSidePanel, setExpandedDocumentFilename, openSidePanelTab]
    );
}
