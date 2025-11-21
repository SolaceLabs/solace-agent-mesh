import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import type { Project } from "@/lib/types/projects";
import type { Session } from "@/lib/types";

interface MoveSessionDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (targetProjectId: string | null) => Promise<void>;
    session: Session | null;
    projects: Project[];
    currentProjectId?: string | null;
}

export const MoveSessionDialog = ({ isOpen, onClose, onConfirm, session, projects, currentProjectId }: MoveSessionDialogProps) => {
    const [selectedProjectId, setSelectedProjectId] = useState<string | null | "">(null);
    const [isMoving, setIsMoving] = useState(false);

    // Reset selected project when dialog opens
    useEffect(() => {
        if (isOpen) {
            setSelectedProjectId("");
        }
    }, [isOpen]);

    if (!isOpen || !session) {
        return null;
    }

    const handleConfirm = async () => {
        setIsMoving(true);
        try {
            await onConfirm(selectedProjectId);
            onClose();
        } catch (error) {
            console.error("Failed to move session:", error);
        } finally {
            setIsMoving(false);
        }
    };

    // Filter out the current project from the list
    const availableProjects = projects.filter(p => p.id !== currentProjectId);

    const getDescription = () => {
        if (currentProjectId) {
            return `Move "${session.name || "Untitled Session"}" to a different project or remove it from the current project.`;
        }
        return `Move "${session.name || "Untitled Session"}" to a project.`;
    };

    const getNoProjectLabel = () => {
        if (currentProjectId) {
            return "No Project (Remove from current)";
        }
        return "No Project";
    };

    const getPlaceholder = () => {
        if (currentProjectId) {
            return "Select a project";
        }
        return "Select a project to move to";
    };

    // Disable move button if no selection made or if selecting the same state
    const isMoveDisabled = isMoving || selectedProjectId === "" || (selectedProjectId === null && !currentProjectId);

    const handleClose = () => {
        if (!isMoving) {
            onClose();
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleClose()}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Move Chat Session</DialogTitle>
                    <DialogDescription>{getDescription()}</DialogDescription>
                </DialogHeader>
                <div className="py-4">
                    <Select value={selectedProjectId === null ? "none" : selectedProjectId || ""} onValueChange={value => setSelectedProjectId(value === "none" ? null : value)}>
                        <SelectTrigger className="w-full rounded-md">
                            <SelectValue placeholder={getPlaceholder()} />
                        </SelectTrigger>
                        <SelectContent>
                            {currentProjectId && <SelectItem value="none">{getNoProjectLabel()}</SelectItem>}
                            {availableProjects.map(project => (
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
                    <Button onClick={handleConfirm} disabled={isMoveDisabled}>
                        {isMoving ? "Moving..." : "Move"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
