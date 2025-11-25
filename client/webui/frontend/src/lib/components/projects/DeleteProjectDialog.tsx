import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import type { Project } from "@/lib/types/projects";

interface DeleteProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => Promise<void>;
    project: Project | null;
    isDeleting?: boolean;
}

export const DeleteProjectDialog = ({ isOpen, onClose, onConfirm, project, isDeleting = false }: DeleteProjectDialogProps) => {
    if (!project) {
        return null;
    }

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={onClose}
            title="Delete Project"
            content={
                <div>
                    This action cannot be undone. This project and all its associated chat sessions and artifacts will be permanently deleted: <strong>{project.name}</strong>.
                </div>
            }
            actionLabels={{ confirm: "Delete" }}
            onConfirm={onConfirm}
            onCancel={onClose}
            isLoading={isDeleting}
        />
    );
};
