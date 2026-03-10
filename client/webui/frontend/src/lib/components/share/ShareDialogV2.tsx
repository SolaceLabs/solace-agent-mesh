/**
 * ShareDialogV2 component - Manage access dialog with per-user permissions
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Plus, MoreVertical, Eye, Copy, Users, RefreshCw, Trash2, ExternalLink } from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { UserTypeahead } from "../common/UserTypeahead";
import { Input } from "../ui/input";
import { createShareLink, getShareLinkForSession, getShareUsers, addShareUsers, deleteShareUsers } from "../../api/shareApi";
import { useConfigContext } from "../../hooks/useConfigContext";
import type { ShareLink, SharedLinkUserInfo } from "../../types/share";

type AccessLevel = "read-only" | "copy" | "collaborate";

interface AccessLevelOption {
    value: AccessLevel;
    label: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
}

const accessLevelOptions: AccessLevelOption[] = [
    {
        value: "read-only",
        label: "Read Only",
        description: "Share a read-only snapshot for debugging or reference",
        icon: Eye,
    },
    {
        value: "copy",
        label: "Copy of Conversation",
        description: "Give a copy of this chat to teammates to continue working on their own",
        icon: Copy,
    },
    {
        value: "collaborate",
        label: "Collaborate",
        description: "Work together with teammates in real-time with full access",
        icon: Users,
    },
];

// Form schema
const shareFormSchema = z.object({
    viewers: z.array(
        z.object({
            id: z.string(),
            email: z.string().email().nullable(),
            accessLevel: z.enum(["read-only", "copy", "collaborate"]),
        })
    ),
    pendingRemoves: z.array(z.string().email()),
});

type ShareFormData = z.infer<typeof shareFormSchema>;

interface ShareDialogV2Props {
    sessionId: string;
    sessionTitle: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Callback for displaying errors to the user */
    onError?: (error: { title: string; message: string }) => void;
    /** Callback for displaying success notifications */
    onSuccess?: (message: string) => void;
    /** For testing/stories - show add row by default */
    defaultShowAddRow?: boolean;
}

export function ShareDialogV2({ sessionId, sessionTitle, open, onOpenChange, onError, onSuccess, defaultShowAddRow = false }: Readonly<ShareDialogV2Props>) {
    const { identityServiceType } = useConfigContext();
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [sharedUsers, setSharedUsers] = useState<SharedLinkUserInfo[]>([]);
    const [ownerEmail, setOwnerEmail] = useState<string>("");
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [savingUser, setSavingUser] = useState(false);

    const { control, handleSubmit, reset, setValue, watch } = useForm<ShareFormData>({
        resolver: zodResolver(shareFormSchema),
        defaultValues: { viewers: [], pendingRemoves: [] },
        mode: "onBlur",
    });

    const { fields, prepend, remove } = useFieldArray({ control, name: "viewers" });
    const viewers = watch("viewers");
    const pendingRemoves = watch("pendingRemoves");

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
            reset({
                viewers: defaultShowAddRow ? [{ id: `typeahead-${Date.now()}`, email: null, accessLevel: "read-only" }] : [],
                pendingRemoves: [],
            });

            // Auto-generate link if none exists
            loadShareLink().then(async link => {
                if (!link) {
                    try {
                        const newLink = await createShareLink(sessionId, {
                            require_authentication: true,
                        });
                        setShareLink(newLink);
                    } catch (error) {
                        onError?.({ title: "Failed to Create Share Link", message: error instanceof Error ? error.message : "Unknown error" });
                    }
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

    const handleDiscard = () => {
        reset({ viewers: [], pendingRemoves: [] });
        onOpenChange(false);
    };

    const onSubmit = async (data: ShareFormData) => {
        if (!shareLink?.share_id) return;

        setSavingUser(true);
        try {
            const emailsToAdd = data.viewers.filter(v => v.email !== null).map(v => ({ email: v.email as string, accessLevel: v.accessLevel }));

            if (emailsToAdd.length > 0) {
                await addShareUsers(shareLink.share_id, {
                    shares: emailsToAdd.map(item => ({ user_email: item.email })),
                });
                const userText = emailsToAdd.length === 1 ? "user" : "users";
                onSuccess?.(`${emailsToAdd.length} ${userText} added`);
            }

            if (data.pendingRemoves.length > 0) {
                await deleteShareUsers(shareLink.share_id, { user_emails: data.pendingRemoves });
                const userText = data.pendingRemoves.length === 1 ? "user" : "users";
                onSuccess?.(`${data.pendingRemoves.length} ${userText} removed`);
            }

            reset({ viewers: [], pendingRemoves: [] });
            await loadSharedUsers();
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
        return sharedUsers.filter(user => !pendingRemoves.includes(user.user_email));
    }, [sharedUsers, pendingRemoves]);

    const hasChanges = viewers.filter(v => v.email !== null).length > 0 || pendingRemoves.length > 0;
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
                        <p className="text-foreground flex-1 text-sm">Users will be able to see the entire shared chat, including artifacts and conversation history up until the moment the chat was shared.</p>
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
                                    <Label className="text-sm text-(--color-secondary-text-wMain)">Email</Label>
                                </div>
                                <div className="w-full shrink-0 sm:w-[200px]">
                                    <Label className="text-sm text-(--color-secondary-text-wMain)">Access Level</Label>
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
                                                        const SelectedIcon = selectedOption?.icon;
                                                        return (
                                                            <Select value={accessField.value} onValueChange={accessField.onChange}>
                                                                <SelectTrigger className="w-full">
                                                                    <SelectValue>
                                                                        <div className="flex items-center gap-2">
                                                                            {SelectedIcon && <SelectedIcon className="text-muted-foreground h-4 w-4" />}
                                                                            {selectedOption?.label}
                                                                        </div>
                                                                    </SelectValue>
                                                                </SelectTrigger>
                                                                <SelectContent className="w-[280px]">
                                                                    {accessLevelOptions.map(option => {
                                                                        const Icon = option.icon;
                                                                        return (
                                                                            <SelectItem key={option.value} value={option.value}>
                                                                                <div className="flex items-start gap-3 py-1">
                                                                                    <Icon className="text-muted-foreground mt-0.5 h-5 w-5 shrink-0" />
                                                                                    <div className="flex flex-col items-start">
                                                                                        <div className="text-sm font-medium">{option.label}</div>
                                                                                        <div className="text-muted-foreground mt-0.5 text-xs leading-tight">{option.description}</div>
                                                                                    </div>
                                                                                </div>
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
                                <Label className="text-sm text-(--color-secondary-text-wMain)">Email</Label>
                            </div>
                            <div className="w-full shrink-0 sm:w-[200px]">
                                <Label className="text-sm text-(--color-secondary-text-wMain)">Snapshot Time</Label>
                            </div>
                            <div className="w-full shrink-0 sm:w-[200px]">
                                <Label className="text-sm text-(--color-secondary-text-wMain)">Access Level</Label>
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
                                {displayedViewers.map(user => {
                                    const snapshotDate = new Date(user.added_at * 1000);
                                    const formattedDate =
                                        snapshotDate.toLocaleDateString("en-US", {
                                            year: "numeric",
                                            month: "2-digit",
                                            day: "2-digit",
                                        }) +
                                        " " +
                                        snapshotDate.toLocaleTimeString("en-US", {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                            hour12: true,
                                        });

                                    return (
                                        <div key={user.user_email} className="flex items-center gap-4 border-b px-4 py-3 last:border-b-0">
                                            <div className="min-w-0 flex-1 truncate text-sm">{user.user_email}</div>
                                            <div className="flex w-full shrink-0 items-center gap-2 sm:w-[200px]">
                                                <span className="text-muted-foreground text-sm whitespace-nowrap">{formattedDate}</span>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" aria-label="Update snapshot">
                                                            <RefreshCw className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        <p>Update Snapshot</p>
                                                    </TooltipContent>
                                                </Tooltip>
                                            </div>
                                            <div className="w-full shrink-0 sm:w-[200px]">
                                                <Select defaultValue={user.access_level} disabled>
                                                    <SelectTrigger className="w-full">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="read-only">Read Only</SelectItem>
                                                        <SelectItem value="copy">Copy</SelectItem>
                                                        <SelectItem value="collaborate">Collaborate</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" disabled={savingUser}>
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    <DropdownMenuItem>
                                                        <ExternalLink className="mr-2 h-4 w-4" />
                                                        Preview Chat
                                                    </DropdownMenuItem>
                                                    <DropdownMenuItem onClick={() => handleRemoveUser(user.user_email)} className="text-destructive focus:text-destructive">
                                                        <Trash2 className="mr-2 h-4 w-4" />
                                                        Remove Access
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </div>
                                    );
                                })}
                                {/* Owner row (current user) */}
                                {ownerEmail && (
                                    <div className="bg-muted/10 flex items-center gap-4 px-4 py-3">
                                        <div className="min-w-0 flex-1 text-sm">{ownerEmail}</div>
                                        <div className="w-full shrink-0 sm:w-[200px]" /> {/* No snapshot time for owner */}
                                        <div className="text-muted-foreground w-full shrink-0 text-sm sm:w-[200px]">Owner</div>
                                        <div className="w-8 shrink-0" /> {/* Space for alignment */}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>

                <DialogFooter className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={handleDiscard} disabled={savingUser}>
                        Discard Changes
                    </Button>
                    <Button onClick={handleSubmit(onSubmit)} disabled={savingUser || !hasChanges}>
                        Save
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
