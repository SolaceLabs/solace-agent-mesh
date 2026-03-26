/**
 * ShareChatDialog component - Manage access dialog with per-user permissions
 */

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { X, Plus, MoreVertical, RefreshCw, Trash2, ExternalLink, Link2, Check, Copy } from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Spinner } from "../ui/spinner";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { UserTypeahead } from "../common/UserTypeahead";
import { Input } from "../ui/input";
import { useShareLink, useShareUsers, useCreateShareLink, useDeleteShareLink, useAddShareUsers, useDeleteShareUsers, useUpdateShareSnapshot } from "../../api/share";
import { copyToClipboard, copyDeferredToClipboard } from "../../utils/clipboard";
import { api } from "../../api";
import { cn } from "../../utils";
import { useConfigContext } from "../../hooks/useConfigContext";
import type { ShareLink } from "../../types/share";

type AccessLevel = "read-only";

/** Map frontend access level names to backend values */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function toBackendAccessLevel(_level: AccessLevel): string {
    return "RESOURCE_VIEWER";
}

/** Map backend access level values to frontend names */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function toFrontendAccessLevel(_backendLevel: string): AccessLevel {
    return "read-only";
}

interface AccessLevelOption {
    value: AccessLevel;
    label: string;
}

const accessLevelOptions: AccessLevelOption[] = [
    {
        value: "read-only",
        label: "Viewer",
    },
];

// Shared styling for table header labels
const TABLE_HEADER_LABEL_CLASS = "text-sm text-secondary-foreground";

function formatDateYMD(epochMs: number): string {
    const d = new Date(epochMs);
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
}

// Form schema
const shareFormSchema = z.object({
    viewers: z.array(
        z.object({
            id: z.string(),
            email: z.string().email().nullable(),
            accessLevel: z.enum(["read-only"]),
        })
    ),
    pendingRemoves: z.array(z.string().email()),
    accessLevelChanges: z.array(
        z.object({
            email: z.string().email(),
            newAccessLevel: z.enum(["read-only"]),
        })
    ),
});

type ShareFormData = z.infer<typeof shareFormSchema>;

interface ShareChatDialogProps {
    sessionId: string;
    sessionTitle: string;
    /** ISO timestamp of when the session was last updated (optional, defaults to current time) */
    sessionUpdatedTime?: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Callback for displaying errors to the user */
    onError?: (error: { title: string; message: string }) => void;
    /** Callback for displaying success notifications */
    onSuccess?: (message: string) => void;
    /** For testing/stories - show add row by default */
    defaultShowAddRow?: boolean;
    /** For testing/stories - show public link section by default */
    defaultShowPublicLink?: boolean;
}

export function ShareChatDialog({ sessionId, sessionTitle, sessionUpdatedTime, open, onOpenChange, onError, onSuccess, defaultShowAddRow = false, defaultShowPublicLink = false }: Readonly<ShareChatDialogProps>) {
    const { identityServiceType } = useConfigContext();

    // React Query hooks for data fetching
    const shareLinkQuery = useShareLink(sessionId);
    const shareUsersQuery = useShareUsers(shareLinkQuery.data?.shareId);
    const createShareLinkMutation = useCreateShareLink();
    const deleteShareLinkMutation = useDeleteShareLink();
    const addShareUsersMutation = useAddShareUsers();
    const deleteShareUsersMutation = useDeleteShareUsers();
    const updateSnapshotMutation = useUpdateShareSnapshot();

    // Derived state from React Query
    const shareLink: ShareLink | null = shareLinkQuery.data ?? null;
    const sharedUsers = shareUsersQuery.data?.users ?? [];
    const ownerEmail = shareUsersQuery.data?.ownerEmail ?? "";
    const loadingUsers = shareUsersQuery.isLoading;
    const isSaving = createShareLinkMutation.isPending || addShareUsersMutation.isPending || deleteShareUsersMutation.isPending;

    // Session detail query for snapshot outdated detection
    const sessionDetailQuery = useQuery({
        queryKey: ["sessions", "detail", sessionId],
        queryFn: () => api.webui.get(`/api/v1/sessions/${sessionId}`),
        enabled: open && !!sessionId,
    });
    const sessionLastUpdateMs: number | null = (sessionDetailQuery.data as { data?: { updatedTime?: number } })?.data?.updatedTime ?? null;

    // UI-only local state
    const [showPublicLink, setShowPublicLink] = useState(defaultShowPublicLink);
    const [publicLinkCopied, setPublicLinkCopied] = useState(false);
    const [footerLinkCopied, setFooterLinkCopied] = useState(false);
    const [creatingLink, setCreatingLink] = useState(false);
    const [isNewlyCreatedLink, setIsNewlyCreatedLink] = useState(false);
    const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Track the newly created share ID in a ref so discard can always find it,
    // even during the async gap between createShareLink and setState.
    const newlyCreatedShareIdRef = useRef<string | null>(null);

    const { control, handleSubmit, reset, setValue, watch } = useForm<ShareFormData>({
        resolver: zodResolver(shareFormSchema),
        defaultValues: { viewers: [], pendingRemoves: [], accessLevelChanges: [] },
        mode: "onBlur",
    });

    const { fields, prepend, remove } = useFieldArray({ control, name: "viewers" });
    const viewers = watch("viewers");
    const pendingRemoves = watch("pendingRemoves");
    const accessLevelChanges = watch("accessLevelChanges");

    // Reset state when dialog opens
    useEffect(() => {
        if (!open) return;

        setIsNewlyCreatedLink(false);
        setShowPublicLink(defaultShowPublicLink || !!shareLinkQuery.data);
        setFooterLinkCopied(false);
        setPublicLinkCopied(false);
        setCreatingLink(false);
        newlyCreatedShareIdRef.current = null;
        if (copiedTimerRef.current) {
            clearTimeout(copiedTimerRef.current);
            copiedTimerRef.current = null;
        }

        reset({
            viewers: defaultShowAddRow ? [{ id: `typeahead-${Date.now()}`, email: null, accessLevel: "read-only" }] : [],
            pendingRemoves: [],
            accessLevelChanges: [],
        });

        // Refetch data when dialog opens
        shareLinkQuery.refetch();
        sessionDetailQuery.refetch();
    }, [open, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleAddRow = useCallback(() => {
        const newId = `typeahead-${Date.now()}`;
        prepend({ id: newId, email: null, accessLevel: "read-only" });
    }, [prepend]);

    const handleRemoveRow = useCallback(
        (id: string) => {
            const index = fields.findIndex(f => f.id === id);
            if (index !== -1) {
                remove(index);
            }
        },
        [fields, remove]
    );

    const handleRemoveUser = (email: string) => {
        setValue("pendingRemoves", [...pendingRemoves, email]);
    };

    const handleAccessLevelChange = (email: string, newAccessLevel: AccessLevel) => {
        const existingChangeIndex = accessLevelChanges.findIndex(change => change.email === email);

        if (existingChangeIndex >= 0) {
            // Update existing change
            const updated = [...accessLevelChanges];
            updated[existingChangeIndex] = { email, newAccessLevel };
            setValue("accessLevelChanges", updated);
        } else {
            // Add new change
            setValue("accessLevelChanges", [...accessLevelChanges, { email, newAccessLevel }]);
        }
    };

    const handleCopyPublicLink = async () => {
        // Generate share link if it doesn't exist
        if (!shareLink) {
            setCreatingLink(true);

            // Start the clipboard write synchronously (before any await) so the
            // browser still considers this a user-gesture context.
            const linkPromise = createShareLinkMutation.mutateAsync({
                sessionId,
                options: { require_authentication: false },
            });
            const clipboardOk = copyDeferredToClipboard(linkPromise.then(link => link.shareUrl));

            try {
                const newLink = await linkPromise;
                newlyCreatedShareIdRef.current = newLink.shareId;
                setIsNewlyCreatedLink(true);

                const success = await clipboardOk;
                if (success) {
                    setFooterLinkCopied(true);
                    setPublicLinkCopied(true);
                    onSuccess?.("Public link created and copied to clipboard");
                    // Brief delay so user sees the "Copied!" state on the footer button
                    copiedTimerRef.current = setTimeout(() => {
                        copiedTimerRef.current = null;
                        setFooterLinkCopied(false);
                        setPublicLinkCopied(false);
                        setShowPublicLink(true);
                    }, 1500);
                } else {
                    setShowPublicLink(true);
                    onSuccess?.("Public link created");
                }
            } catch (error) {
                onError?.({ title: "Failed to Create Public Link", message: error instanceof Error ? error.message : "Unknown error" });
            } finally {
                setCreatingLink(false);
            }
            return;
        }

        // Copy existing link
        const success = await copyToClipboard(shareLink.shareUrl);
        if (success) {
            setPublicLinkCopied(true);
            if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
            copiedTimerRef.current = setTimeout(() => {
                copiedTimerRef.current = null;
                setPublicLinkCopied(false);
            }, 2000);
            setShowPublicLink(true);
            onSuccess?.("Link copied to clipboard");
        }
    };

    const handleDeletePublicLink = async () => {
        if (shareLink?.shareId) {
            try {
                await deleteShareLinkMutation.mutateAsync(shareLink.shareId);
                setIsNewlyCreatedLink(false);
            } catch (error) {
                onError?.({ title: "Failed to Delete Link", message: error instanceof Error ? error.message : "Unknown error" });
                return;
            }
        }
        setShowPublicLink(false);
        onSuccess?.("Link removed");
    };

    const handleUpdateUserSnapshot = async (userEmail: string) => {
        if (!shareLink?.shareId) return;

        try {
            await updateSnapshotMutation.mutateAsync({
                shareId: shareLink.shareId,
                userEmail,
            });
            onSuccess?.(`Snapshot updated for ${userEmail}`);
        } catch (error) {
            onError?.({ title: "Failed to Update Snapshot", message: error instanceof Error ? error.message : "Unknown error" });
        }
    };

    const handleDiscard = useCallback(async () => {
        // Cancel any pending "Copied!" timer so it doesn't re-show the link section
        if (copiedTimerRef.current) {
            clearTimeout(copiedTimerRef.current);
            copiedTimerRef.current = null;
        }
        // If the link was newly created and user discards, delete it.
        // Use the ref as single source of truth (avoids stale closure issues).
        const shareIdToDelete = newlyCreatedShareIdRef.current;
        if (shareIdToDelete) {
            try {
                await deleteShareLinkMutation.mutateAsync(shareIdToDelete);
                setIsNewlyCreatedLink(false);
                setShowPublicLink(false);
                newlyCreatedShareIdRef.current = null;
                onSuccess?.("Share link removed");
            } catch (error) {
                console.error("Failed to delete share link on discard:", error);
            }
        }
        reset({ viewers: [], pendingRemoves: [], accessLevelChanges: [] });
        onOpenChange(false);
    }, [onOpenChange, reset, onSuccess, deleteShareLinkMutation]);

    // Intercept dialog close (X button, backdrop click, Escape) to clean up newly created links
    const handleOpenChange = useCallback(
        (nextOpen: boolean) => {
            if (!nextOpen && newlyCreatedShareIdRef.current) {
                handleDiscard();
                return;
            }
            onOpenChange(nextOpen);
        },
        [onOpenChange, handleDiscard]
    );

    const onSubmit = async (data: ShareFormData) => {
        try {
            // Create share link on-demand if it doesn't exist yet
            let activeShareLink = shareLink;
            let linkCreatedInSubmit = false;
            if (!activeShareLink?.shareId) {
                const newLink = await createShareLinkMutation.mutateAsync({
                    sessionId,
                    options: { require_authentication: true },
                });
                activeShareLink = newLink;
                linkCreatedInSubmit = true;
                // Keep ref so discard can clean up if a later step fails
                newlyCreatedShareIdRef.current = newLink.shareId;
            }
            if (!activeShareLink?.shareId) {
                onError?.({ title: "Failed to Save", message: "Could not create share link" });
                return;
            }

            const emailsToAdd = data.viewers.filter(v => v.email !== null).map(v => ({ email: v.email as string, accessLevel: v.accessLevel }));

            if (emailsToAdd.length > 0) {
                await addShareUsersMutation.mutateAsync({
                    shareId: activeShareLink.shareId,
                    data: {
                        shares: emailsToAdd.map(item => ({
                            user_email: item.email,
                            access_level: toBackendAccessLevel(item.accessLevel),
                        })),
                    },
                });
                const userText = emailsToAdd.length === 1 ? "user" : "users";
                onSuccess?.(`${emailsToAdd.length} ${userText} added`);
            }

            if (data.pendingRemoves.length > 0) {
                await deleteShareUsersMutation.mutateAsync({
                    shareId: activeShareLink.shareId,
                    data: { user_emails: data.pendingRemoves },
                });
                const userText = data.pendingRemoves.length === 1 ? "user" : "users";
                onSuccess?.(`${data.pendingRemoves.length} ${userText} removed`);
            }

            if (data.accessLevelChanges.length > 0) {
                await addShareUsersMutation.mutateAsync({
                    shareId: activeShareLink.shareId,
                    data: {
                        shares: data.accessLevelChanges.map(change => ({
                            user_email: change.email,
                            access_level: toBackendAccessLevel(change.newAccessLevel),
                        })),
                    },
                });
                onSuccess?.(`Access levels updated for ${data.accessLevelChanges.length} user(s)`);
            }

            // All operations succeeded — clear newly-created tracking
            if (linkCreatedInSubmit) {
                setIsNewlyCreatedLink(false);
                newlyCreatedShareIdRef.current = null;
            }
            reset({ viewers: [], pendingRemoves: [], accessLevelChanges: [] });
            onOpenChange(false);
        } catch (error) {
            onError?.({ title: "Failed to Save Changes", message: error instanceof Error ? error.message : "Unknown error" });
        }
    };

    const excludedEmails = useMemo(() => {
        const existingEmails = sharedUsers.map(u => u.userEmail);
        const pendingEmails = viewers.map(v => v.email).filter((e): e is string => e !== null);
        return [...existingEmails, ...pendingEmails];
    }, [sharedUsers, viewers]);

    const displayedViewers = useMemo(() => {
        return sharedUsers.filter(user => !pendingRemoves.includes(user.userEmail)).sort((a, b) => a.userEmail.localeCompare(b.userEmail));
    }, [sharedUsers, pendingRemoves]);

    const hasChanges = viewers.filter(v => v.email !== null).length > 0 || pendingRemoves.length > 0 || accessLevelChanges.length > 0 || isNewlyCreatedLink;
    const hasIncompleteRows = viewers.some(v => v.email === null);

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden sm:max-w-[818px]">
                <DialogHeader>
                    <DialogTitle className="mb-4 text-xl">
                        <span className="font-bold">Manage Access:</span> <span className="font-normal">{sessionTitle}</span>
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 space-y-6 overflow-y-auto">
                    {/* Description + Add Button */}
                    <div className="flex items-start justify-between gap-6">
                        <p className="text-foreground flex-1 text-sm">Users will see a snapshot of the shared chat, including files and conversation history.</p>
                        <Button variant="outline" size="sm" onClick={handleAddRow} disabled={hasIncompleteRows || isSaving} className="shrink-0">
                            <Plus className="mr-2 h-4 w-4" />
                            Add
                        </Button>
                    </div>

                    {/* Add User Rows */}
                    {fields.length > 0 && (
                        <div className="mb-4 space-y-4">
                            {/* Headers for add rows only */}
                            <div className="mb-1 flex items-end gap-4">
                                <div className="min-w-0 flex-1">
                                    <Label className={TABLE_HEADER_LABEL_CLASS}>Email</Label>
                                </div>
                                <div className="w-full shrink-0 sm:w-[200px]">
                                    <Label className={TABLE_HEADER_LABEL_CLASS}>Access Level</Label>
                                </div>
                                <div className="w-8 shrink-0" /> {/* Space for X button */}
                            </div>

                            {fields.map((field, index) => (
                                <Controller
                                    key={field.id}
                                    control={control}
                                    name={`viewers.${index}.email`}
                                    render={({ field: { value, onChange } }) => (
                                        <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center">
                                            {/* Email field - takes remaining space */}
                                            <div className="min-w-0 flex-1">
                                                {identityServiceType !== null ? (
                                                    <UserTypeahead id={field.id} onSelect={email => onChange(email)} onRemove={() => handleRemoveRow(field.id)} excludeEmails={excludedEmails} selectedEmail={value} hideRoleBadge hideCloseButton />
                                                ) : (
                                                    <Input type="email" placeholder="Enter email address..." value={value || ""} onChange={e => onChange(e.target.value || null)} />
                                                )}
                                            </div>
                                            {/* Access Level */}
                                            <div className="w-full shrink-0 sm:w-[200px]">
                                                <Controller
                                                    control={control}
                                                    name={`viewers.${index}.accessLevel`}
                                                    render={({ field: accessField }) => {
                                                        const selectedOption = accessLevelOptions.find(opt => opt.value === accessField.value);
                                                        return (
                                                            <Select value={accessField.value} onValueChange={accessField.onChange}>
                                                                <SelectTrigger className="w-full">
                                                                    <SelectValue>{selectedOption?.label}</SelectValue>
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {accessLevelOptions.map(option => {
                                                                        return (
                                                                            <SelectItem key={option.value} value={option.value}>
                                                                                {option.label}
                                                                            </SelectItem>
                                                                        );
                                                                    })}
                                                                </SelectContent>
                                                            </Select>
                                                        );
                                                    }}
                                                />
                                            </div>
                                            {/* Remove button */}
                                            <Button variant="ghost" size="icon" className="shrink-0" onClick={() => handleRemoveRow(field.id)} aria-label="Remove user row">
                                                <X className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    )}
                                />
                            ))}
                        </div>
                    )}

                    {/* Existing Users Table */}
                    <div className="rounded border">
                        {/* Table Header */}
                        <div className="bg-muted/30 flex items-center gap-4 border-b px-4 py-2">
                            <div className="min-w-0 flex-1">
                                <Label className={TABLE_HEADER_LABEL_CLASS}>Email</Label>
                            </div>
                            <div className="w-full shrink-0 sm:w-[200px]">
                                <Label className={TABLE_HEADER_LABEL_CLASS}>Shared On</Label>
                            </div>
                            <div className="w-full shrink-0 sm:w-[200px]">
                                <Label className={TABLE_HEADER_LABEL_CLASS}>Access Level</Label>
                            </div>
                            <div className="w-8 shrink-0" /> {/* Space for action buttons */}
                        </div>

                        {/* User Rows */}
                        {loadingUsers ? (
                            <div className="flex justify-center py-8">
                                <Spinner size="small" variant="muted" />
                            </div>
                        ) : (
                            <>
                                {/* Owner row (current user) - always shown first */}
                                <div className="bg-muted/10 flex items-center gap-4 border-b px-4 py-3">
                                    <div className="min-w-0 flex-1 text-sm">{ownerEmail || "You"}</div>
                                    <div className="w-full shrink-0 sm:w-[200px]" /> {/* No snapshot time for owner */}
                                    <div className="text-muted-foreground w-full shrink-0 text-sm sm:w-[200px]">Owner</div>
                                    <div className="w-8 shrink-0" /> {/* Space for alignment */}
                                </div>
                                {displayedViewers.map(user => {
                                    const formattedDate = formatDateYMD(user.addedAt);

                                    // Check if snapshot is outdated (session was updated after user was added)
                                    const effectiveLastUpdate = sessionLastUpdateMs || (sessionUpdatedTime ? new Date(sessionUpdatedTime).getTime() : null);
                                    const isSnapshotOutdated = effectiveLastUpdate !== null && effectiveLastUpdate > user.addedAt;
                                    const isUpdatingThisUser = updateSnapshotMutation.isPending && updateSnapshotMutation.variables?.userEmail === user.userEmail;

                                    return (
                                        <div key={user.userEmail} className="flex items-center gap-4 border-b px-4 py-3 last:border-b-0">
                                            <div className="min-w-0 flex-1 truncate text-sm">{user.userEmail}</div>
                                            <div className="flex w-full shrink-0 items-center gap-2 sm:w-[200px]">
                                                <span className="text-muted-foreground text-sm whitespace-nowrap">{formattedDate}</span>
                                                {isSnapshotOutdated && (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-6 w-6 shrink-0"
                                                                aria-label="Update snapshot"
                                                                disabled={updateSnapshotMutation.isPending}
                                                                onClick={() => handleUpdateUserSnapshot(user.userEmail)}
                                                            >
                                                                <RefreshCw className={cn("h-3.5 w-3.5", isUpdatingThisUser && "animate-spin")} />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent>
                                                            <p>Update Snapshot</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                )}
                                            </div>
                                            <div className="w-full shrink-0 sm:w-[200px]">
                                                {(() => {
                                                    const change = accessLevelChanges.find(c => c.email === user.userEmail);
                                                    const currentValue = change?.newAccessLevel || toFrontendAccessLevel(user.accessLevel);
                                                    const selectedOption = accessLevelOptions.find(opt => opt.value === currentValue);

                                                    return (
                                                        <Select value={currentValue} onValueChange={value => handleAccessLevelChange(user.userEmail, value as AccessLevel)}>
                                                            <SelectTrigger className="w-full">
                                                                <SelectValue>{selectedOption?.label}</SelectValue>
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {accessLevelOptions.map(option => {
                                                                    return (
                                                                        <SelectItem key={option.value} value={option.value}>
                                                                            {option.label}
                                                                        </SelectItem>
                                                                    );
                                                                })}
                                                            </SelectContent>
                                                        </Select>
                                                    );
                                                })()}
                                            </div>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" disabled={isSaving} aria-label="User actions">
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => shareLink && window.open(shareLink.shareUrl, "_blank")}>
                                                        Preview Chat
                                                        <ExternalLink className="mr-2 h-4 w-4" />
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => handleRemoveUser(user.userEmail)}>Remove Access</DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </div>
                                    );
                                })}
                            </>
                        )}
                    </div>

                    {/* Public Link Section - only shown if public link exists */}
                    {showPublicLink && shareLink && (
                        <div className="bg-muted rounded p-4">
                            <div className="mb-4 flex items-start justify-between">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <Link2 className="h-4 w-4" />
                                        <Label className="text-sm font-bold">Sharing Link</Label>
                                    </div>
                                    <p className="text-muted-foreground mt-1 text-sm">Anyone in your organization with this link can view the chat in a read-only mode.</p>
                                </div>
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" aria-label="Link actions">
                                            <MoreVertical className="h-4 w-4" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                        <DropdownMenuItem onClick={() => shareLink && window.open(shareLink.shareUrl, "_blank")}>
                                            <ExternalLink className="mr-2 h-4 w-4" />
                                            Preview Chat
                                        </DropdownMenuItem>
                                        <DropdownMenuItem onClick={handleDeletePublicLink} className="text-destructive focus:text-destructive">
                                            <Trash2 className="mr-2 h-4 w-4" />
                                            Remove Public Link
                                        </DropdownMenuItem>
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>

                            <div className="flex items-center gap-4">
                                <div className="relative min-w-0 flex-1">
                                    <div className="bg-background truncate rounded border px-3 py-2 pr-10 font-mono text-xs">{shareLink.shareUrl}</div>
                                    <Button variant="ghost" size="icon" className="absolute top-1/2 right-1 h-6 w-6 -translate-y-1/2" onClick={handleCopyPublicLink}>
                                        {publicLinkCopied ? <Check className="h-4 w-4 text-(--success-wMain)" /> : <Copy className="h-4 w-4" />}
                                    </Button>
                                </div>
                                <div className="flex shrink-0 flex-col items-start px-4">
                                    <span className="text-muted-foreground text-xs">Shared On</span>
                                    <div className="flex items-center gap-1">
                                        <span className="text-sm whitespace-nowrap">{formatDateYMD(shareLink.createdTime)}</span>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-5 w-5"
                                                    aria-label="Refresh public link snapshot"
                                                    onClick={() =>
                                                        shareLink &&
                                                        updateSnapshotMutation
                                                            .mutateAsync({ shareId: shareLink.shareId })
                                                            .then(() => onSuccess?.("Snapshot updated"))
                                                            .catch(err => onError?.({ title: "Failed to Update Snapshot", message: err instanceof Error ? err.message : "Unknown error" }))
                                                    }
                                                >
                                                    <RefreshCw className="h-3.5 w-3.5" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>Update Snapshot</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="flex justify-between gap-2">
                    {/* Public Link Button - left side */}
                    {!showPublicLink && (
                        <Button variant="ghost" size="sm" onClick={handleCopyPublicLink} disabled={creatingLink}>
                            {footerLinkCopied ? (
                                <>
                                    <Check className="mr-2 h-4 w-4 text-(--success-wMain)" />
                                    Copied!
                                </>
                            ) : creatingLink ? (
                                <>
                                    <Spinner size="small" variant="muted" className="mr-2" />
                                    Creating Link...
                                </>
                            ) : (
                                <>
                                    <Link2 className="mr-2 h-4 w-4" />
                                    Copy Sharing Link
                                </>
                            )}
                        </Button>
                    )}
                    <div className="flex-1" />

                    {/* Save/Discard - right side */}
                    <div className="flex gap-2">
                        <Button variant="ghost" onClick={handleDiscard} disabled={isSaving}>
                            Discard Changes
                        </Button>
                        <Button onClick={handleSubmit(onSubmit)} disabled={isSaving || !hasChanges}>
                            Save
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

/** @deprecated Use ShareChatDialog instead */
export const ShareDialog = ShareChatDialog;
