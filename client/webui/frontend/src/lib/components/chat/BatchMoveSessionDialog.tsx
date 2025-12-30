import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import type { Project } from "@/lib/types/projects";

interface BatchMoveSessionDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (targetProjectId: string | null) => Promise<void>;
    sessionCount: number;
    projects: Project[];
}

export const BatchMoveSessionDialog = ({ isOpen, onClose, onConfirm, sessionCount, projects }: BatchMoveSessionDialogProps) => {
    const [selectedProjectId, setSelectedProjectId] = useState<string | null | "">(null);
    const [isMoving, setIsMoving] = useState(false);

    // Reset selected project when dialog opens
    useEffect(() => {
        if (isOpen) {
            setSelectedProjectId("");
        }
    }, [isOpen]);

    if (!isOpen) {
        return null;
    }

    const handleConfirm = async () => {
        setIsMoving(true);
        try {
            await onConfirm(selectedProjectId === "none" ? null : selectedProjectId || null);
            onClose();
        } catch (error) {
            console.error("Failed to batch move sessions:", error);
        } finally {
            setIsMoving(false);
        }
    };

    const getDescription = () => {
        return `Move ${sessionCount} selected chat${sessionCount > 1 ? "s" : ""} to a project or remove from their current projects.`;
    };

    // Disable move button if no selection made
    const isMoveDisabled = isMoving || selectedProjectId === "";

    const handleClose = () => {
        if (!isMoving) {
            onClose();
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleClose()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>
                        Move {sessionCount} Chat{sessionCount > 1 ? "s" : ""}
                    </DialogTitle>
                    <DialogDescription>{getDescription()}</DialogDescription>
                </DialogHeader>
                <div className="py-4">
                    <Select value={selectedProjectId === null ? "none" : selectedProjectId || ""} onValueChange={value => setSelectedProjectId(value === "none" ? null : value)}>
                        <SelectTrigger className="w-full rounded-md">
                            <SelectValue placeholder="Select a project" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="none">No Project (Remove from current)</SelectItem>
                            {projects.map(project => (
                                <SelectItem key={project.id} value={project.id}>
                                    <p className="max-w-sm truncate">{project.name}</p>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleClose} disabled={isMoving}>
                        Cancel
                    </Button>
                    <Button variant="outline" onClick={handleConfirm} disabled={isMoveDisabled}>
                        {isMoving ? "Moving..." : `Move ${sessionCount} Chat${sessionCount > 1 ? "s" : ""}`}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
