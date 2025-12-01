import React from "react";
import { AlertTriangle } from "lucide-react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Button } from "@/lib/components/ui";

interface SkillDeleteConfirmDialogProps {
    open: boolean;
    skillName: string;
    isDeleting: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

export const SkillDeleteConfirmDialog: React.FC<SkillDeleteConfirmDialogProps> = ({ open, skillName, isDeleting, onConfirm, onCancel }) => {
    return (
        <Dialog open={open} onOpenChange={isOpen => !isOpen && !isDeleting && onCancel()}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertTriangle className="text-destructive h-5 w-5" />
                        Delete Skill
                    </DialogTitle>
                </DialogHeader>

                <div className="py-4">
                    <p className="text-sm">
                        Are you sure you want to delete <span className="font-semibold">"{skillName}"</span>?
                    </p>
                    <p className="text-muted-foreground mt-2 text-sm">This will permanently delete the skill and all its versions. This action cannot be undone.</p>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={onCancel} disabled={isDeleting}>
                        Cancel
                    </Button>
                    <Button variant="destructive" onClick={onConfirm} disabled={isDeleting}>
                        {isDeleting ? "Deleting..." : "Delete"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
