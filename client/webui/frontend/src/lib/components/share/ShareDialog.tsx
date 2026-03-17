/**
 * ShareDialog component - Manage access dialog with per-user permissions
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Plus, MoreVertical, RefreshCw, Trash2, ExternalLink, Link2, Check, Copy } from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { UserTypeahead } from "../common/UserTypeahead";
import { Input } from "../ui/input";
import { createShareLink, getShareLinkForSession, deleteShareLink, getShareUsers, addShareUsers, deleteShareUsers, copyToClipboard, updateShareSnapshot } from "../../api/shareApi";
import { api } from "../../api";
import { useConfigContext } from "../../hooks/useConfigContext";
import type { ShareLink, SharedLinkUserInfo } from "../../types/share";

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

interface ShareDialogProps {
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

export function ShareDialog({ sessionId, sessionTitle, sessionUpdatedTime, open, onOpenChange, onError, onSuccess, defaultShowAddRow = false, defaultShowPublicLink = false }: Readonly<ShareDialogProps>) {
    const { identityServiceType } = useConfigContext();
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [sharedUsers, setSharedUsers] = useState<SharedLinkUserInfo[]>([]);
    const [ownerEmail, setOwnerEmail] = useState<string>("");
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [savingUser, setSavingUser] = useState(false);
    const [showPublicLink, setShowPublicLink] = useState(defaultShowPublicLink);
    const [publicLinkCopied, setPublicLinkCopied] = useState(false);
    const [isNewlyCreatedLink, setIsNewlyCreatedLink] = useState(false);
    const [updatingSnapshotEmail, setUpdatingSnapshotEmail] = useState<string | null>(null);
    const [sessionLastUpdateMs, setSessionLastUpdateMs] = useState<number | null>(null);

    const { control, handleSubmit, reset, setValue, watch } = useForm<ShareFormData>({
        resolver: zodResolver(shareFormSchema),
        defaultValues: { viewers: [], pendingRemoves: [], accessLevelChanges: [] },
        mode: "onBlur",
    });

    const { fields, prepend, remove } = useFieldArray({ control, name: "viewers" });
    const viewers = watch("viewers");
    const pendingRemoves = watch("pendingRemoves");
    const accessLevelChanges = watch("accessLevelChanges");

    // Load share link for the session
    const loadShareLink = useCallback(async () => {
        try {
            const link = await getShareLinkForSession(sessionId);
            if (link) {
                setShareLink(link);
            }
            return link;
        } catch (error) {
            console.error("Failed to load share link:", error);
            return null;
        }
    }, [sessionId]);

    // Load shared users for the share link
    const loadSharedUsers = useCallback(async () => {
        if (!shareLink?.share_id) return;
        setLoadingUsers(true);
        try {
            const response = await getShareUsers(shareLink.share_id);
            setSharedUsers(response.users);
            setOwnerEmail(response.owner_email);
        } catch (error) {
            console.error("Failed to load shared users:", error);
            onError?.({ title: "Failed to Load Shared Users", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setLoadingUsers(false);
        }
    }, [shareLink?.share_id, onError]);

    // Reset state when dialog opens
    useEffect(() => {
        if (open) {
            setShareLink(null);
            setSharedUsers([]);
            setOwnerEmail("");
            setIsNewlyCreatedLink(false);
            setSessionLastUpdateMs(null);

            // Fetch session's updated_time for snapshot outdated check
            api.webui
                .get(`/api/v1/sessions/${sessionId}`)
                .then((data: { data?: { updatedTime?: number } }) => {
                    if (data?.data?.updatedTime) {
                        setSessionLastUpdateMs(data.data.updatedTime);
                    }
                })
                .catch(() => {
                    /* ignore */
                });

            reset({
                viewers: defaultShowAddRow ? [{ id: `typeahead-${Date.now()}`, email: null, accessLevel: "read-only" }] : [],
                pendingRemoves: [],
                accessLevelChanges: [],
            });

            // Load existing share link (if any) - don't auto-create
            // Link is created on-demand when user clicks "Copy Link" or adds users
            loadShareLink().then(link => {
                if (link) {
                    setIsNewlyCreatedLink(false);
                    setShowPublicLink(true); // Show the link section if a link already exists
                }
            });
        }
    }, [open, sessionId, defaultShowAddRow, loadShareLink, onError, reset]);

    // Load shared users when share link is available
    useEffect(() => {
        if (shareLink?.share_id) {
            loadSharedUsers();
        }
    }, [shareLink?.share_id, loadSharedUsers]);

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
            try {
                const newLink = await createShareLink(sessionId, {
                    require_authentication: false, // Public link = no auth required
                });
                setShareLink(newLink);
                setIsNewlyCreatedLink(true);

                // Copy to clipboard
                const success = await copyToClipboard(newLink.share_url);
                if (success) {
                    setPublicLinkCopied(true);
                    setTimeout(() => setPublicLinkCopied(false), 2000);
                    setShowPublicLink(true);
                    onSuccess?.("Public link created and copied to clipboard");
                }
            } catch (error) {
                onError?.({ title: "Failed to Create Public Link", message: error instanceof Error ? error.message : "Unknown error" });
            }
            return;
        }

        // Copy existing link
        const success = await copyToClipboard(shareLink.share_url);
        if (success) {
            setPublicLinkCopied(true);
            setTimeout(() => setPublicLinkCopied(false), 2000);
            setShowPublicLink(true);
            onSuccess?.("Link copied to clipboard");
        }
    };

    const handleDeletePublicLink = async () => {
        // Actually delete the link from the backend
        if (shareLink?.share_id) {
            try {
                await deleteShareLink(shareLink.share_id);
                setShareLink(null);
                setIsNewlyCreatedLink(false);
            } catch (error) {
                console.error("Failed to delete share link:", error);
            }
        }
        setShowPublicLink(false);
        onSuccess?.("Link removed");
    };

    const handleUpdateUserSnapshot = async (userEmail: string) => {
        if (!shareLink?.share_id || updatingSnapshotEmail) return;

        setUpdatingSnapshotEmail(userEmail);
        try {
            await updateShareSnapshot(shareLink.share_id, userEmail);
            onSuccess?.(`Snapshot updated for ${userEmail}`);
            await loadSharedUsers();
        } catch (error) {
            onError?.({ title: "Failed to Update Snapshot", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setUpdatingSnapshotEmail(null);
        }
    };

    const handleDiscard = async () => {
        // If the link was newly created and user discards, delete it
        if (isNewlyCreatedLink && shareLink?.share_id) {
            try {
                await deleteShareLink(shareLink.share_id);
                setShareLink(null);
                setIsNewlyCreatedLink(false);
                setShowPublicLink(false);
                onSuccess?.("Share link removed");
            } catch (error) {
                console.error("Failed to delete share link on discard:", error);
            }
        }
        reset({ viewers: [], pendingRemoves: [], accessLevelChanges: [] });
        onOpenChange(false);
    };

    const onSubmit = async (data: ShareFormData) => {
        setSavingUser(true);
        try {
            // Create share link on-demand if it doesn't exist yet
            let activeShareLink = shareLink;
            if (!activeShareLink?.share_id) {
                const newLink = await createShareLink(sessionId, { require_authentication: true });
                setShareLink(newLink);
                setIsNewlyCreatedLink(false); // It's being saved, so it's no longer "newly created"
                activeShareLink = newLink;
            }
            if (!activeShareLink?.share_id) {
                onError?.({ title: "Failed to Save", message: "Could not create share link" });
                return;
            }

            const emailsToAdd = data.viewers.filter(v => v.email !== null).map(v => ({ email: v.email as string, accessLevel: v.accessLevel }));

            if (emailsToAdd.length > 0) {
                await addShareUsers(activeShareLink.share_id, {
                    shares: emailsToAdd.map(item => ({
                        user_email: item.email,
                        access_level: toBackendAccessLevel(item.accessLevel),
                    })),
                });
                const userText = emailsToAdd.length === 1 ? "user" : "users";
                onSuccess?.(`${emailsToAdd.length} ${userText} added`);
            }

            if (data.pendingRemoves.length > 0) {
                await deleteShareUsers(activeShareLink.share_id, { user_emails: data.pendingRemoves });
                const userText = data.pendingRemoves.length === 1 ? "user" : "users";
                onSuccess?.(`${data.pendingRemoves.length} ${userText} removed`);
            }

            if (data.accessLevelChanges.length > 0) {
                await addShareUsers(activeShareLink.share_id, {
                    shares: data.accessLevelChanges.map(change => ({
                        user_email: change.email,
                        access_level: toBackendAccessLevel(change.newAccessLevel),
                    })),
                });
                onSuccess?.(`Access levels updated for ${data.accessLevelChanges.length} user(s)`);
            }

            reset({ viewers: [], pendingRemoves: [], accessLevelChanges: [] });
            await loadSharedUsers();
            window.dispatchEvent(new CustomEvent("share-updated", { detail: { sessionId } }));
            onOpenChange(false);
        } catch (error) {
            onError?.({ title: "Failed to Save Changes", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setSavingUser(false);
        }
    };

    const excludedEmails = useMemo(() => {
        const existingEmails = sharedUsers.map(u => u.user_email);
        const pendingEmails = viewers.map(v => v.email).filter((e): e is string => e !== null);
        return [...existingEmails, ...pendingEmails];
    }, [sharedUsers, viewers]);

    const displayedViewers = useMemo(() => {
        return sharedUsers.filter(user => !pendingRemoves.includes(user.user_email)).sort((a, b) => a.user_email.localeCompare(b.user_email));
    }, [sharedUsers, pendingRemoves]);

    const hasChanges = viewers.filter(v => v.email !== null).length > 0 || pendingRemoves.length > 0 || accessLevelChanges.length > 0 || isNewlyCreatedLink || showPublicLink;
    const hasIncompleteRows = viewers.some(v => v.email === null);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
                        <Button variant="outline" size="sm" onClick={handleAddRow} disabled={hasIncompleteRows || savingUser} className="shrink-0">
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
                                            <Button variant="ghost" size="icon" className="shrink-0" onClick={() => handleRemoveRow(field.id)}>
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
                                <div className="border-primary h-5 w-5 animate-spin rounded-full border-2 border-t-transparent" />
                            </div>
                        ) : (
                            <>
                                {/* Owner row (current user) - always shown first */}
                                {ownerEmail && (
                                    <div className="bg-muted/10 flex items-center gap-4 border-b px-4 py-3">
                                        <div className="min-w-0 flex-1 text-sm">{ownerEmail}</div>
                                        <div className="w-full shrink-0 sm:w-[200px]" /> {/* No snapshot time for owner */}
                                        <div className="text-muted-foreground w-full shrink-0 text-sm sm:w-[200px]">Owner</div>
                                        <div className="w-8 shrink-0" /> {/* Space for alignment */}
                                    </div>
                                )}
                                {displayedViewers.map(user => {
                                    const snapshotDate = new Date(user.added_at);
                                    const formattedDate = `${snapshotDate.getFullYear()}/${String(snapshotDate.getMonth() + 1).padStart(2, "0")}/${String(snapshotDate.getDate()).padStart(2, "0")}`;

                                    // Check if snapshot is outdated (session was updated after user was added)
                                    const effectiveLastUpdate = sessionLastUpdateMs || (sessionUpdatedTime ? new Date(sessionUpdatedTime).getTime() : null);
                                    const isSnapshotOutdated = effectiveLastUpdate !== null && effectiveLastUpdate > user.added_at;
                                    const isUpdatingThisUser = updatingSnapshotEmail === user.user_email;

                                    return (
                                        <div key={user.user_email} className="flex items-center gap-4 border-b px-4 py-3 last:border-b-0">
                                            <div className="min-w-0 flex-1 truncate text-sm">{user.user_email}</div>
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
                                                                disabled={isUpdatingThisUser || !!updatingSnapshotEmail}
                                                                onClick={() => handleUpdateUserSnapshot(user.user_email)}
                                                            >
                                                                <RefreshCw className={`h-3.5 w-3.5 ${isUpdatingThisUser ? "animate-spin" : ""}`} />
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
                                                    const change = accessLevelChanges.find(c => c.email === user.user_email);
                                                    const currentValue = change?.newAccessLevel || toFrontendAccessLevel(user.access_level);
                                                    const selectedOption = accessLevelOptions.find(opt => opt.value === currentValue);

                                                    return (
                                                        <Select value={currentValue} onValueChange={value => handleAccessLevelChange(user.user_email, value as AccessLevel)}>
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
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" disabled={savingUser}>
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem onClick={() => shareLink && window.open(shareLink.share_url, "_blank")}>
                                                        Preview Chat
                                                        <ExternalLink className="mr-2 h-4 w-4" />
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => handleRemoveUser(user.user_email)}>Remove Access</DropdownMenuItem>
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
                                        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                                            <MoreVertical className="h-4 w-4" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                        <DropdownMenuItem onClick={() => shareLink && window.open(shareLink.share_url, "_blank")}>
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
                                    <div className="bg-background truncate rounded border px-3 py-2 pr-10 font-mono text-xs">{shareLink.share_url}</div>
                                    <Button variant="ghost" size="icon" className="absolute top-1/2 right-1 h-6 w-6 -translate-y-1/2" onClick={handleCopyPublicLink}>
                                        {publicLinkCopied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                                    </Button>
                                </div>
                                <div className="flex shrink-0 flex-col items-start px-4">
                                    <span className="text-muted-foreground text-xs">Shared On</span>
                                    <div className="flex items-center gap-1">
                                        <span className="text-sm whitespace-nowrap">
                                            {(() => {
                                                const d = new Date(shareLink.created_time);
                                                return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
                                            })()}
                                        </span>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button variant="ghost" size="icon" className="h-5 w-5" aria-label="Refresh public link snapshot">
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
                        <Button variant="ghost" size="sm" onClick={handleCopyPublicLink}>
                            <Link2 className="mr-2 h-4 w-4" />
                            Copy Sharing Link
                        </Button>
                    )}
                    <div className="flex-1" />

                    {/* Save/Discard - right side */}
                    <div className="flex gap-2">
                        <Button variant="ghost" onClick={handleDiscard} disabled={savingUser}>
                            Discard Changes
                        </Button>
                        <Button onClick={handleSubmit(onSubmit)} disabled={savingUser || !hasChanges}>
                            Save
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
