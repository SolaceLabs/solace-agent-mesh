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

export const MoveSessionDialog = ({
    isOpen,
    onClose,
    onConfirm,
    session,
    projects,
    currentProjectId
}: MoveSessionDialogProps) => {
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
    const [isMoving, setIsMoving] = useState(false);

    // Reset selected project when dialog opens
    useEffect(() => {
        if (isOpen) {
            setSelectedProjectId(null);
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

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Move Chat Session</DialogTitle>
                    <DialogDescription>
                        Move "{session.name || 'Untitled Session'}" to a different project or remove it from the current project.
                    </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                    <Select
                        value={selectedProjectId || "none"}
                        onValueChange={(value) => setSelectedProjectId(value === "none" ? null : value)}
                    >
                        <SelectTrigger className="rounded-md">
                            <SelectValue placeholder="Select a project" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="none">No Project (Remove from current)</SelectItem>
                            {availableProjects.map((project) => (
                                <SelectItem key={project.id} value={project.id}>
                                    {project.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={onClose} disabled={isMoving}>
                        Cancel
                    </Button>
                    <Button onClick={handleConfirm} disabled={isMoving}>
                        {isMoving ? "Moving..." : "Move"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};