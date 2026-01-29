import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, X, Loader2 } from "lucide-react";

import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { MessageBanner } from "@/lib/components/common";
import { UserTypeahead } from "@/lib/components/common/UserTypeahead";
import { useProjectShares, useCreateProjectShares, useDeleteProjectShares } from "@/lib/api/projects/hooks";
import { shareProjectFormSchema, type ShareProjectFormData } from "@/lib/schemas";
import type { Project } from "@/lib/types/projects";

interface ShareProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    project: Project;
}

export const ShareProjectDialog: React.FC<ShareProjectDialogProps> = ({ isOpen, onClose, project }) => {
    const [error, setError] = useState<string | null>(null);

    // React Hook Form setup
    const { control, handleSubmit, reset, setValue, watch, trigger } = useForm<ShareProjectFormData>({
        resolver: zodResolver(shareProjectFormSchema),
        defaultValues: { viewers: [], pendingRemoves: [] },
        mode: "onChange",
    });

    const { fields, append, remove } = useFieldArray({ control, name: "viewers" });
    const viewers = watch("viewers");
    const pendingRemoves = watch("pendingRemoves");

    // Fetch current shares
    const { data: sharesData, isLoading: isLoadingShares } = useProjectShares(project.id);

    // Mutations
    const createSharesMutation = useCreateProjectShares();
    const deleteSharesMutation = useDeleteProjectShares();

    const isSaving = createSharesMutation.isPending || deleteSharesMutation.isPending;

    // Reset state when dialog opens
    useEffect(() => {
        if (isOpen) {
            reset({ viewers: [], pendingRemoves: [] });
            setError(null);
        }
    }, [isOpen, reset]);

    // Compute the current list of viewers to display (only saved users, not pending)
    const displayedViewers = useMemo(() => {
        return (sharesData?.shares || [])
            .filter(share => !pendingRemoves.includes(share.userEmail))
            .map(share => ({
                email: share.userEmail,
                isPending: false,
            }));
    }, [sharesData?.shares, pendingRemoves]);

    // All emails that should be excluded from the typeahead
    const excludeEmails = useMemo(() => {
        const ownerEmail = sharesData?.ownerEmail || "";
        const existingEmails = (sharesData?.shares || []).map(s => s.userEmail);
        const pendingEmails = viewers.map(v => v.email).filter((e): e is string => e !== null);
        return [ownerEmail, ...existingEmails, ...pendingEmails].filter(Boolean);
    }, [sharesData?.ownerEmail, sharesData?.shares, viewers]);

    // Check if there are any pending changes (use watched viewers for current values)
    const pendingAdds = viewers.filter(v => v.email !== null).map(v => v.email as string);
    const hasChanges = pendingAdds.length > 0 || pendingRemoves.length > 0;

    // Check if any typeaheads have incomplete selections
    const hasIncompleteTypeaheads = viewers.some(v => v.email === null);

    // Add a new typeahead instance
    const handleAddTypeahead = useCallback(() => {
        const newId = `typeahead-${Date.now()}`;
        append({ id: newId, email: null });
    }, [append]);

    // Remove a typeahead instance
    const handleRemoveTypeahead = useCallback(
        (id: string) => {
            const index = fields.findIndex(f => f.id === id);
            if (index !== -1) {
                remove(index);
            }
        },
        [fields, remove]
    );

    const handleAddUser = useCallback(
        (email: string, _typeaheadId: string, fieldIndex: number, onChange: (value: string | null) => void) => {
            // Clear selection if empty email (user is re-editing)
            if (!email) {
                onChange(null);
                return;
            }

            // Don't add the owner
            if (email === sharesData?.ownerEmail) {
                setError("Cannot add the project owner as a viewer");
                return;
            }

            // Check if trying to re-add a removed user (restore behavior)
            if (pendingRemoves.includes(email)) {
                // Remove from pendingRemoves and remove the typeahead field
                setValue(
                    "pendingRemoves",
                    pendingRemoves.filter(e => e !== email)
                );
                // Remove the typeahead since the user was restored from pending removes
                remove(fieldIndex);
            } else {
                // Update the field with the selected email
                onChange(email);
            }
        },
        [sharesData?.ownerEmail, pendingRemoves, setValue, remove]
    );

    const handleRemoveUser = (email: string) => {
        // Add to pending removes (only for saved users, pending ones are removed via typeahead)
        setValue("pendingRemoves", [...pendingRemoves, email]);
    };

    const handleDiscard = () => {
        reset({ viewers: [], pendingRemoves: [] });
        setError(null);
        onClose();
    };

    const onSubmit = async (data: ShareProjectFormData) => {
        setError(null);

        // Validate all typeaheads have selections
        const hasIncomplete = data.viewers.some(v => !v.email);
        if (hasIncomplete) {
            // Form will show errors via formState.errors
            return;
        }

        try {
            const emailsToAdd = data.viewers.filter(v => v.email !== null).map(v => v.email as string);

            // Process additions
            if (emailsToAdd.length > 0) {
                await createSharesMutation.mutateAsync({
                    projectId: project.id,
                    data: {
                        shares: emailsToAdd.map(email => ({
                            userEmail: email,
                            accessLevel: "RESOURCE_VIEWER" as const,
                        })),
                    },
                });
            }

            // Process removals
            if (data.pendingRemoves.length > 0) {
                await deleteSharesMutation.mutateAsync({
                    projectId: project.id,
                    data: {
                        userEmails: data.pendingRemoves,
                    },
                });
            }

            // Reset state and close
            reset({ viewers: [], pendingRemoves: [] });
            onClose();
        } catch (err) {
            console.error("Failed to save project shares:", err);
            setError(err instanceof Error ? err.message : "Failed to save changes");
        }
    };

    const handleSave = async () => {
        const isValid = await trigger();
        if (!isValid) {
            return;
        }
        handleSubmit(onSubmit)();
    };

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleDiscard()}>
            <DialogContent className="flex max-h-[80vh] flex-col sm:max-w-xl">
                <DialogHeader className="mb-6 flex-shrink-0">
                    <DialogTitle>Share Project</DialogTitle>
                    <div className="flex items-center justify-between">
                        <DialogDescription>
                            Invite others to collaborate on <strong>{project.name}</strong>.
                        </DialogDescription>
                        <Button variant="outline" size="default" onClick={handleAddTypeahead} disabled={isSaving || hasIncompleteTypeaheads} className="gap-1">
                            <Plus className="h-4 w-4" />
                            Add
                        </Button>
                    </div>
                </DialogHeader>

                {error && (
                    <div className="flex-shrink-0 py-2">
                        <MessageBanner variant="error" message={error} />
                    </div>
                )}

                {/* Scrollable Content Area */}
                <div className="min-h-0 flex-1 overflow-y-auto">
                    {isLoadingShares ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="h-6 w-6 animate-spin text-[var(--muted-foreground)]" />
                        </div>
                    ) : fields.length === 0 && !sharesData?.ownerEmail && displayedViewers.length === 0 ? (
                        <div className="py-8 text-center text-sm text-[var(--muted-foreground)]">No users have access to this project yet.</div>
                    ) : (
                        <div className="flex flex-col divide-[var(--border)]">
                            {/* Header Row */}
                            <div className="grid grid-cols-[1fr_85px_32px] items-center gap-x-3 pb-2">
                                <span className="text-xs font-medium text-[var(--muted-foreground)]">Email</span>
                                <span className="text-center text-xs font-medium text-[var(--muted-foreground)]">Access Level</span>
                                <div />
                            </div>

                            {/* Pending Typeaheads with Controller */}
                            {fields.map((field, index) => (
                                <Controller
                                    key={field.id}
                                    control={control}
                                    name={`viewers.${index}.email`}
                                    render={({ field: { value, onChange }, fieldState: { error: fieldError } }) => (
                                        <div className="py-3 pr-3">
                                            <div className="grid grid-cols-[1fr_85px_32px] items-center gap-x-1">
                                                <UserTypeahead
                                                    id={field.id}
                                                    onSelect={(email: string) => handleAddUser(email, field.id, index, onChange)}
                                                    onRemove={() => handleRemoveTypeahead(field.id)}
                                                    excludeEmails={excludeEmails}
                                                    selectedEmail={value}
                                                    error={!!fieldError}
                                                />
                                            </div>
                                            {fieldError && <p className="mt-1 text-xs text-[var(--destructive)]">{fieldError.message}</p>}
                                        </div>
                                    )}
                                />
                            ))}

                            {/* Owner Row - Always First */}
                            {sharesData?.ownerEmail && (
                                <div className={`grid grid-cols-[1fr_85px_32px] items-center border py-3 ${displayedViewers.length === 0 ? "rounded-sm" : "rounded-t-sm border-b-0"} px-3`}>
                                    <span className="truncate text-sm">{sharesData.ownerEmail}</span>
                                    <Badge variant="secondary" className="justify-self-center">
                                        Owner
                                    </Badge>
                                    <div className="h-8 w-8" />
                                </div>
                            )}

                            {/* Viewer Rows */}
                            {displayedViewers.map((viewer, index) => (
                                <div key={viewer.email} className={`grid grid-cols-[1fr_85px_32px] items-center border px-3 py-3 ${index === displayedViewers.length - 1 ? "rounded-b-sm" : "border-b-0"}`}>
                                    <span className="truncate text-sm">{viewer.email}</span>
                                    <Badge title="Can view the items in the project" variant="secondary" className="justify-self-center">
                                        Viewer
                                    </Badge>
                                    <Button variant="ghost" size="sm" onClick={() => handleRemoveUser(viewer.email)} disabled={isSaving} className="h-8 w-8 p-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                                        <X className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <DialogFooter className="flex-shrink-0">
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
