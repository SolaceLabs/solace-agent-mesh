import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import type { Project } from "@/lib/types/projects";

interface DeleteProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => Promise<void>;
    project: Project | null;
    isDeleting?: boolean;
}

export const DeleteProjectDialog = ({ 
    isOpen, 
    onClose, 
    onConfirm, 
    project,
    isDeleting = false 
}: DeleteProjectDialogProps) => {
    if (!isOpen || !project) {
        return null;
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete Project?</DialogTitle>
                    <DialogDescription>
                        Are you sure you want to delete the project <strong>"{project.name}"</strong>?
                        <br /><br />
                        This will remove the project and all its associated chat sessions and artifacts. This action cannot be undone.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="ghost" onClick={onClose} disabled={isDeleting}>
                        Cancel
                    </Button>
                    <Button
                        variant="outline"
                        onClick={onConfirm}
                        disabled={isDeleting}
                    >
                        {isDeleting ? "Deleting..." : "Delete Project"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};