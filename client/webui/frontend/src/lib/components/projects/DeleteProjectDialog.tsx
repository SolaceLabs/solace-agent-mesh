import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";
import type { Project } from "@/lib/types/projects";

interface DeleteProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => Promise<void>;
    project: Project | null;
    isProjectSharingEnabled?: boolean;
    isDeleting?: boolean;
}

export const DeleteProjectDialog = ({ isOpen, onClose, onConfirm, project, isProjectSharingEnabled = false, isDeleting = false }: DeleteProjectDialogProps) => {
    if (!project) {
        return null;
    }

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && onClose()}
            title="Delete Project"
            content={
                <>
                    {isProjectSharingEnabled ? (
                        <>
                            Chat sessions in (<strong>{project.name}</strong>) will be permanently deleted for all users this project is shared with.
                        </>
                    ) : (
                        <>
                            All chat sessions inside this project (<strong>{project.name}</strong>) will be permanently deleted.
                        </>
                    )}
                    <br />
                    <br />
                    This action cannot be undone.
                </>
            }
            actionLabels={{ confirm: "Delete" }}
            onConfirm={onConfirm}
            onCancel={onClose}
            isLoading={isDeleting}
        />
    );
};
