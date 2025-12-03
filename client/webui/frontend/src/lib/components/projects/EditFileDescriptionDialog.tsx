import React, { useState, useEffect } from "react";
import { FileText } from "lucide-react";

import { Button, Card, Textarea } from "@/lib/components/ui";
import { CardContent } from "@/lib/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import type { ArtifactInfo } from "@/lib/types";

interface EditFileDescriptionDialogProps {
    isOpen: boolean;
    artifact: ArtifactInfo | null;
    onClose: () => void;
    onSave: (description: string) => Promise<void>;
    isSaving?: boolean;
}

export const EditFileDescriptionDialog: React.FC<EditFileDescriptionDialogProps> = ({ isOpen, artifact, onClose, onSave, isSaving = false }) => {
    const [description, setDescription] = useState("");

    useEffect(() => {
        if (isOpen && artifact) {
            setDescription(artifact.description || "");
        }
    }, [isOpen, artifact]);

    const handleSave = async () => {
        await onSave(description);
    };

    const handleCancel = () => {
        setDescription(artifact?.description || "");
        onClose();
    };

    if (!artifact) return null;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle>Edit File Description</DialogTitle>
                    <DialogDescription>Update the description for this file to help Solace Agent Mesh understand its purpose.</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <Card noPadding className="bg-muted/50 overflow-hidden py-3 shadow-none">
                        <CardContent noPadding className="overflow-hidden px-3">
                            <div className="flex min-w-0 items-center gap-3">
                                <FileText className="text-muted-foreground h-4 w-4 flex-shrink-0" />
                                <div className="min-w-0 flex-1 overflow-hidden">
                                    <p className="text-foreground line-clamp-2 text-sm font-medium break-all" title={artifact.filename}>
                                        {artifact.filename}
                                    </p>
                                    <p className="text-muted-foreground text-xs">{(artifact.size / 1024).toFixed(1)} KB</p>
                                </div>
                            </div>
                            <Textarea className="bg-background text-foreground mt-2" rows={2} disabled={isSaving} value={description} onChange={e => setDescription(e.target.value)} placeholder="Enter a description for this file..." />
                        </CardContent>
                    </Card>
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel} disabled={isSaving}>
                        Discard Changes
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving ? "Saving..." : "Save"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
