import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Plus, X, Loader2 } from "lucide-react";

import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { MessageBanner } from "@/lib/components/common";
import { UserTypeahead } from "@/lib/components/common/UserTypeahead";
import { useProjectShares, useCreateProjectShares, useDeleteProjectShares } from "@/lib/api/projects/hooks";
import type { Project } from "@/lib/types/projects";

interface ShareProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    project: Project;
}

export const ShareProjectDialog: React.FC<ShareProjectDialogProps> = ({ isOpen, onClose, project }) => {
    const [pendingAdds, setPendingAdds] = useState<string[]>([]);
    const [pendingRemoves, setPendingRemoves] = useState<string[]>([]);
    const [typeaheadIds, setTypeaheadIds] = useState<string[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Fetch current shares
    const { data: sharesData, isLoading: isLoadingShares } = useProjectShares(project.id);

    // Mutations
    const createSharesMutation = useCreateProjectShares();
    const deleteSharesMutation = useDeleteProjectShares();

    const isSaving = createSharesMutation.isPending || deleteSharesMutation.isPending;

    // Reset state when dialog opens
    useEffect(() => {
        if (isOpen) {
            setPendingAdds([]);
            setPendingRemoves([]);
            setTypeaheadIds([]);
            setError(null);
        }
    }, [isOpen]);

    // Compute the current list of viewers to display
    const displayedViewers = useMemo(() => {
        const existingViewers = (sharesData?.shares || [])
            .filter(share => !pendingRemoves.includes(share.userEmail))
            .map(share => ({
                email: share.userEmail,
                isPending: false,
            }));

        const pendingViewers = pendingAdds.map(email => ({
            email,
            isPending: true,
        }));

        return [...existingViewers, ...pendingViewers];
    }, [sharesData?.shares, pendingAdds, pendingRemoves]);

    // All emails that should be excluded from the typeahead
    const excludeEmails = useMemo(() => {
        const ownerEmail = sharesData?.ownerEmail || "";
        const existingEmails = (sharesData?.shares || []).map(s => s.userEmail);
        return [ownerEmail, ...existingEmails, ...pendingAdds].filter(Boolean);
    }, [sharesData?.ownerEmail, sharesData?.shares, pendingAdds]);

    // Check if there are any pending changes
    const hasChanges = pendingAdds.length > 0 || pendingRemoves.length > 0;

    // Add a new typeahead instance
    const handleAddTypeahead = useCallback(() => {
        const newId = `typeahead-${Date.now()}`;
        setTypeaheadIds(prev => [newId, ...prev]);
    }, []);

    // Remove a typeahead instance
    const handleRemoveTypeahead = useCallback((id: string) => {
        setTypeaheadIds(prev => prev.filter(tid => tid !== id));
    }, []);

    const handleAddUser = useCallback(
        (email: string) => {
            // Don't add the owner
            if (email === sharesData?.ownerEmail) {
                setError("Cannot add the project owner as a viewer");
                return;
            }

            // Check if trying to re-add a removed user
            if (pendingRemoves.includes(email)) {
                setPendingRemoves(prev => prev.filter(e => e !== email));
            } else if (!pendingAdds.includes(email)) {
                setPendingAdds(prev => [...prev, email]);
            }
        },
        [sharesData?.ownerEmail, pendingRemoves, pendingAdds]
    );

    const handleRemoveUser = (email: string, isPending: boolean) => {
        if (isPending) {
            // Remove from pending adds
            setPendingAdds(prev => prev.filter(e => e !== email));
        } else {
            // Add to pending removes
            setPendingRemoves(prev => [...prev, email]);
        }
    };

    const handleDiscard = () => {
        setPendingAdds([]);
        setPendingRemoves([]);
        setTypeaheadIds([]);
        setError(null);
        onClose();
    };

    const handleSave = async () => {
        setError(null);

        try {
            // Process additions
            if (pendingAdds.length > 0) {
                await createSharesMutation.mutateAsync({
                    projectId: project.id,
                    data: {
                        shares: pendingAdds.map(email => ({
                            userEmail: email,
                            accessLevel: "RESOURCE_VIEWER" as const,
                        })),
                    },
                });
            }

            // Process removals
            if (pendingRemoves.length > 0) {
                await deleteSharesMutation.mutateAsync({
                    projectId: project.id,
                    data: {
                        userEmails: pendingRemoves,
                    },
                });
            }

            // Reset state and close
            setPendingAdds([]);
            setPendingRemoves([]);
            setTypeaheadIds([]);
            onClose();
        } catch (err) {
            console.error("Failed to save project shares:", err);
            setError(err instanceof Error ? err.message : "Failed to save changes");
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleDiscard()}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <DialogTitle>Share Project</DialogTitle>
                        <Button variant="outline" size="sm" onClick={handleAddTypeahead} disabled={isSaving} className="gap-1">
                            <Plus className="h-4 w-4" />
                            Add
                        </Button>
                    </div>
                    <DialogDescription>
                        Invite others to collaborate on <strong>{project.name}</strong>.
                    </DialogDescription>
                </DialogHeader>

                {error && (
                    <div className="py-2">
                        <MessageBanner variant="error" message={error} />
                    </div>
                )}

                {/* Typeahead Inputs */}
                {typeaheadIds.length > 0 && (
                    <div className="flex flex-col gap-2">
                        {typeaheadIds.map(id => (
                            <UserTypeahead key={id} id={id} onSelect={handleAddUser} onRemove={handleRemoveTypeahead} excludeEmails={excludeEmails} disabled={isSaving} />
                        ))}
                    </div>
                )}

                {/* User List */}
                <div className="max-h-[300px] overflow-y-auto">
                    {isLoadingShares ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-[var(--muted-foreground)]" />
                        </div>
                    ) : (
                        <div className="divide-y divide-[var(--border)]">
                            {/* Owner Row - Always First */}
                            {sharesData?.ownerEmail && (
                                <div className="flex items-center justify-between py-3">
                                    <span className="text-sm">{sharesData.ownerEmail}</span>
                                    <Badge variant="secondary">Owner</Badge>
                                </div>
                            )}

                            {/* Viewer Rows */}
                            {displayedViewers.map(viewer => (
                                <div key={viewer.email} className="flex items-center justify-between py-3">
                                    <span className="text-sm">{viewer.email}</span>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline">Viewer</Badge>
                                        <Button variant="ghost" size="sm" onClick={() => handleRemoveUser(viewer.email, viewer.isPending)} disabled={isSaving} className="h-8 w-8 p-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                                            <X className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                            ))}

                            {/* Empty State */}
                            {!sharesData?.ownerEmail && displayedViewers.length === 0 && <div className="py-8 text-center text-sm text-[var(--muted-foreground)]">No users have access to this project yet.</div>}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={handleDiscard} disabled={isSaving}>
                        Discard Changes
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving || !hasChanges}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
