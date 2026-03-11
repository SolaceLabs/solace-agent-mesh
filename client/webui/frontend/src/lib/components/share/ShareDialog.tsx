/**
 * ShareDialog component - Manage access dialog for sharing chat sessions
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { Copy, Check, X, Loader2, Plus, Users, Trash2, ExternalLink, Link2, MoreVertical } from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { UserTypeahead } from "../common/UserTypeahead";
import { createShareLink, getShareLinkForSession, deleteShareLink, copyToClipboard, getShareUsers, addShareUsers, deleteShareUsers } from "../../api/shareApi";
import { useConfigContext } from "../../hooks/useConfigContext";
import type { ShareLink, SharedLinkUserInfo } from "../../types/share";

interface ShareDialogProps {
    sessionId: string;
    sessionTitle: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Callback for displaying errors to the user */
    onError?: (error: { title: string; message: string }) => void;
    /** Callback for displaying success notifications */
    onSuccess?: (message: string) => void;
}

export function ShareDialog({ sessionId, sessionTitle, open, onOpenChange, onError, onSuccess }: ShareDialogProps) {
    const { identityServiceType } = useConfigContext();
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // People sharing state
    const [sharedUsers, setSharedUsers] = useState<SharedLinkUserInfo[]>([]);
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [newUserEmail, setNewUserEmail] = useState<string | null>(null);
    const [savingUser, setSavingUser] = useState(false);
    const [showAddUser, setShowAddUser] = useState(false);

    // Load share link for the session, auto-creating one if it doesn't exist
    const loadShareLink = useCallback(async () => {
        setLoading(true);
        try {
            // Try to load existing share link
            const existingLink = await getShareLinkForSession(sessionId);
            if (existingLink) {
                setShareLink(existingLink);
                return;
            }

            // No existing link — auto-create one
            const newLink = await createShareLink(sessionId, {
                require_authentication: true,
            });
            setShareLink(newLink);
            // Auto-copy to clipboard on creation
            await copyToClipboard(newLink.share_url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            onSuccess?.("Share link created and copied!");
        } catch (error) {
            console.error("Failed to load/create share link:", error);
            onError?.({ title: "Failed to Share Chat", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setLoading(false);
        }
    }, [sessionId, onError, onSuccess]);

    // Load shared users for the share link
    const loadSharedUsers = useCallback(async () => {
        if (!shareLink?.share_id) return;
        setLoadingUsers(true);
        try {
            const response = await getShareUsers(shareLink.share_id);
            setSharedUsers(response.users);
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
            setCopied(false);
            setSharedUsers([]);
            setNewUserEmail(null);
            setShowAddUser(false);
            loadShareLink();
        }
    }, [open, sessionId, loadShareLink]);

    // Load shared users when share link is available
    useEffect(() => {
        if (shareLink?.share_id) {
            loadSharedUsers();
        }
    }, [shareLink?.share_id, loadSharedUsers]);

    const handleDeleteShare = async () => {
        if (!shareLink) return;
        setLoading(true);
        try {
            await deleteShareLink(shareLink.share_id);
            setShareLink(null);
            setSharedUsers([]);
            setShowDeleteConfirm(false);
            onSuccess?.("Share link deleted");
            onOpenChange(false);
        } catch (error) {
            onError?.({ title: "Failed to Delete Share Link", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setLoading(false);
        }
    };

    const handleCopyUrl = async () => {
        if (!shareLink) return;
        const success = await copyToClipboard(shareLink.share_url);
        if (success) {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            onSuccess?.("Link copied to clipboard");
        }
    };

    const handleAddUser = async () => {
        if (!shareLink?.share_id || !newUserEmail) return;
        setSavingUser(true);
        try {
            await addShareUsers(shareLink.share_id, {
                shares: [{ user_email: newUserEmail }],
            });
            setNewUserEmail(null);
            setShowAddUser(false);
            await loadSharedUsers();
            onSuccess?.("User added");
        } catch (error) {
            onError?.({ title: "Failed to Add User", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setSavingUser(false);
        }
    };

    const handleRemoveUser = async (email: string) => {
        if (!shareLink?.share_id) return;
        setSavingUser(true);
        try {
            await deleteShareUsers(shareLink.share_id, { user_emails: [email] });
            setSharedUsers(prev => prev.filter(user => user.user_email !== email));
            onSuccess?.("User removed");
        } catch (error) {
            onError?.({ title: "Failed to Remove User", message: error instanceof Error ? error.message : "Unknown error" });
        } finally {
            setSavingUser(false);
        }
    };

    const excludeEmails = useMemo(() => sharedUsers.map(u => u.user_email), [sharedUsers]);

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="flex max-h-[85vh] flex-col overflow-hidden sm:max-w-[600px]" showCloseButton>
                    <DialogHeader>
                        <DialogTitle className="text-lg">
                            <span className="font-bold">Manage Access:</span> <span className="font-normal">{sessionTitle}</span>
                        </DialogTitle>
                    </DialogHeader>

                    {shareLink ? (
                        <div className="flex-1 space-y-5 overflow-y-auto">
                            {/* Description */}
                            <p className="text-muted-foreground text-sm">Users will be able to see the entire shared chat, including artifacts and conversation history up until the moment the chat was shared.</p>

                            {/* Share Link Section */}
                            <div className="bg-muted/40 rounded p-4">
                                <div className="mb-3 flex items-start justify-between">
                                    <div className="flex items-center gap-2">
                                        <Link2 className="h-4 w-4" />
                                        <Label className="text-sm font-bold">Share Link</Label>
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
                                            <DropdownMenuItem onClick={() => setShowDeleteConfirm(true)} className="text-destructive focus:text-destructive">
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Remove Share Link
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </div>

                                <div className="flex items-center gap-3">
                                    <div className="relative min-w-0 flex-1">
                                        <div className="bg-background truncate rounded border px-3 py-2 pr-10 font-mono text-xs">{shareLink.share_url}</div>
                                        <Button variant="ghost" size="icon" className="absolute top-1/2 right-1 h-6 w-6 -translate-y-1/2" onClick={handleCopyUrl}>
                                            {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                                        </Button>
                                    </div>
                                    <div className="flex shrink-0 flex-col items-start">
                                        <span className="text-muted-foreground text-xs">Created</span>
                                        <span className="text-sm whitespace-nowrap">
                                            {new Date(shareLink.created_time).toLocaleDateString("en-US", {
                                                month: "2-digit",
                                                day: "2-digit",
                                                year: "numeric",
                                            })}
                                        </span>
                                    </div>
                                </div>

                                <p className="text-muted-foreground mt-2 text-xs">Anyone with this link who is logged in can view the chat.</p>
                            </div>

                            {/* People Section */}
                            <div>
                                <div className="mb-3 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Users className="h-4 w-4" />
                                        <Label className="text-sm font-bold">People with access</Label>
                                    </div>
                                    {!showAddUser && (
                                        <Button variant="outline" size="sm" onClick={() => setShowAddUser(true)} disabled={savingUser} className="shrink-0">
                                            <Plus className="mr-2 h-4 w-4" />
                                            Add
                                        </Button>
                                    )}
                                </div>

                                {/* Add User Input */}
                                {showAddUser && (
                                    <div className="mb-3 flex items-center gap-2">
                                        {identityServiceType !== null ? (
                                            <div className="min-w-0 flex-1">
                                                <UserTypeahead
                                                    id="add-user"
                                                    onSelect={setNewUserEmail}
                                                    onRemove={() => {
                                                        setNewUserEmail(null);
                                                        setShowAddUser(false);
                                                    }}
                                                    excludeEmails={excludeEmails}
                                                    selectedEmail={newUserEmail}
                                                    hideRoleBadge
                                                    hideCloseButton
                                                />
                                            </div>
                                        ) : (
                                            <Input placeholder="Enter email address..." value={newUserEmail || ""} onChange={e => setNewUserEmail(e.target.value)} className="flex-1" autoFocus />
                                        )}
                                        <Button size="sm" onClick={handleAddUser} disabled={!newUserEmail || savingUser}>
                                            {savingUser ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add"}
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="shrink-0"
                                            onClick={() => {
                                                setNewUserEmail(null);
                                                setShowAddUser(false);
                                            }}
                                        >
                                            <X className="h-4 w-4" />
                                        </Button>
                                    </div>
                                )}

                                {/* User Table */}
                                <div className="rounded border">
                                    {/* Table Header */}
                                    <div className="bg-muted/30 flex items-center gap-4 border-b px-4 py-2">
                                        <div className="min-w-0 flex-1">
                                            <Label className="text-muted-foreground text-xs">Email</Label>
                                        </div>
                                        <div className="w-[100px] shrink-0">
                                            <Label className="text-muted-foreground text-xs">Shared On</Label>
                                        </div>
                                        <div className="w-8 shrink-0" />
                                    </div>

                                    {/* User Rows */}
                                    {loadingUsers ? (
                                        <div className="flex justify-center py-6">
                                            <div className="border-primary h-5 w-5 animate-spin rounded-full border-2 border-t-transparent" />
                                        </div>
                                    ) : sharedUsers.length > 0 ? (
                                        <div className="max-h-48 overflow-y-auto">
                                            {sharedUsers.map(user => {
                                                const sharedDate = new Date(user.added_at).toLocaleDateString("en-US", {
                                                    month: "2-digit",
                                                    day: "2-digit",
                                                    year: "numeric",
                                                });

                                                return (
                                                    <div key={user.user_email} className="flex items-center gap-4 border-b px-4 py-2.5 last:border-b-0">
                                                        <div className="min-w-0 flex-1 truncate text-sm">{user.user_email}</div>
                                                        <div className="text-muted-foreground w-[100px] shrink-0 text-sm">{sharedDate}</div>
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => handleRemoveUser(user.user_email)} disabled={savingUser}>
                                                                    <X className="h-3.5 w-3.5" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent>Remove access</TooltipContent>
                                                        </Tooltip>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="text-muted-foreground py-6 text-center text-xs">No specific people added. Anyone with the link who is logged in can access.</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ) : (
                        /* Loading state while share link is being created */
                        <div className="flex flex-col items-center justify-center gap-3 py-8">
                            <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                            <p className="text-muted-foreground text-sm">Creating share link...</p>
                        </div>
                    )}

                    {shareLink && (
                        <DialogFooter>
                            <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full">
                                Done
                            </Button>
                        </DialogFooter>
                    )}
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation */}
            <ConfirmationDialog
                open={showDeleteConfirm}
                onOpenChange={open => !open && setShowDeleteConfirm(false)}
                title="Delete Share Link"
                content="This will permanently remove the share link. Anyone with the link will no longer be able to access this chat."
                actionLabels={{ confirm: "Delete" }}
                onConfirm={handleDeleteShare}
                onCancel={() => setShowDeleteConfirm(false)}
                isLoading={loading}
            />
        </>
    );
}
