/**
 * ShareDialog component - Modal for managing share links
 */

import { useState, useEffect, useMemo } from "react";
import { Copy, Check, X, Loader2, Link, Users, Shield, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { UserTypeahead } from "../common/UserTypeahead";
import { createShareLink, getShareLinkForSession, updateShareLink, deleteShareLink, copyToClipboard, getShareUsers, addShareUsers, deleteShareUsers } from "../../api/shareApi";
import { useConfigContext } from "../../hooks/useConfigContext";
import type { ShareLink, SharedLinkUserInfo } from "../../types/share";

// Simple notification helper
const showNotification = (message: string, type: "success" | "error" = "success") => {
    console.log(`[${type.toUpperCase()}]`, message);
};

interface ShareDialogProps {
    sessionId: string;
    sessionTitle: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ShareDialog({ sessionId, sessionTitle, open, onOpenChange }: ShareDialogProps) {
    const { identityServiceType } = useConfigContext();
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [requireAuth, setRequireAuth] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // People sharing state
    const [sharedUsers, setSharedUsers] = useState<SharedLinkUserInfo[]>([]);
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [newUserEmail, setNewUserEmail] = useState<string | null>(null);
    const [savingUser, setSavingUser] = useState(false);
    const [showAddUser, setShowAddUser] = useState(false);

    // Reset state when dialog opens
    useEffect(() => {
        if (open) {
            setShareLink(null);
            setRequireAuth(false);
            setCopied(false);
            setSharedUsers([]);
            setNewUserEmail(null);
            setShowAddUser(false);
            loadShareLink();
        }
    }, [open, sessionId]);

    // Load shared users when share link is available
    useEffect(() => {
        if (shareLink?.share_id) {
            loadSharedUsers();
        }
    }, [shareLink?.share_id]);

    const loadShareLink = async () => {
        setLoading(true);
        try {
            const link = await getShareLinkForSession(sessionId);
            if (link) {
                setShareLink(link);
                setRequireAuth(link.require_authentication);
            }
        } catch (error) {
            console.error("Failed to load share link:", error);
        } finally {
            setLoading(false);
        }
    };

    const loadSharedUsers = async () => {
        if (!shareLink?.share_id) return;
        setLoadingUsers(true);
        try {
            const response = await getShareUsers(shareLink.share_id);
            setSharedUsers(response.users);
        } catch (error) {
            console.error("Failed to load shared users:", error);
        } finally {
            setLoadingUsers(false);
        }
    };

    const handleCreateShare = async () => {
        setLoading(true);
        try {
            const link = await createShareLink(sessionId, {
                require_authentication: requireAuth,
            });
            setShareLink(link);
            // Auto-copy to clipboard
            await copyToClipboard(link.share_url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            showNotification("Share link created and copied!", "success");
        } catch (error) {
            showNotification(`Failed to create share link: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteShare = async () => {
        if (!shareLink) return;
        setLoading(true);
        try {
            await deleteShareLink(shareLink.share_id);
            setShareLink(null);
            setRequireAuth(false);
            setSharedUsers([]);
            setShowDeleteConfirm(false);
            showNotification("Share link deleted", "success");
        } catch (error) {
            showNotification(`Failed to delete: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
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
            showNotification("User added", "success");
        } catch (error) {
            showNotification(`Failed to add user: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
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
        } catch (error) {
            showNotification(`Failed to remove user: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
        } finally {
            setSavingUser(false);
        }
    };

    const excludeEmails = useMemo(() => sharedUsers.map(u => u.user_email), [sharedUsers]);

    // Determine access description
    const getAccessDescription = () => {
        if (!shareLink) return null;
        if (sharedUsers.length > 0) {
            return `Shared with ${sharedUsers.length} ${sharedUsers.length === 1 ? "person" : "people"}`;
        }
        if (requireAuth) {
            return "Anyone with the link who is logged in";
        }
        return "Anyone with the link";
    };

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="sm:max-w-[480px]">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <Link className="h-5 w-5" />
                            Share Chat
                        </DialogTitle>
                        <DialogDescription className="truncate">{sessionTitle}</DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-2">
                        {/* Share Link Section */}
                        {shareLink ? (
                            <>
                                {/* URL with Copy and Delete Buttons */}
                                <div className="flex gap-2">
                                    <Input value={shareLink.share_url} readOnly className="flex-1 text-sm" onClick={e => (e.target as HTMLInputElement).select()} />
                                    <Button variant={copied ? "default" : "outline"} size="icon" onClick={handleCopyUrl} className={copied ? "bg-green-600 hover:bg-green-600" : ""} title="Copy link">
                                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                                    </Button>
                                    <Button variant="outline" size="icon" onClick={() => setShowDeleteConfirm(true)} className="text-destructive hover:text-destructive" title="Delete share link">
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>

                                {/* Access Summary */}
                                <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                    <Shield className="h-4 w-4" />
                                    <span>{getAccessDescription()}</span>
                                </div>

                                {/* People Section */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <Label className="flex items-center gap-2 text-sm font-medium">
                                            <Users className="h-4 w-4" />
                                            People with access
                                        </Label>
                                        {!showAddUser && (
                                            <Button variant="ghost" size="sm" onClick={() => setShowAddUser(true)} disabled={savingUser}>
                                                Add person
                                            </Button>
                                        )}
                                    </div>

                                    {/* Add User Input */}
                                    {showAddUser && (
                                        <div className="flex items-center gap-2">
                                            {identityServiceType !== null ? (
                                                <div className="flex-1">
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
                                                <Input placeholder="Enter email address" value={newUserEmail || ""} onChange={e => setNewUserEmail(e.target.value)} className="flex-1" autoFocus />
                                            )}
                                            <Button size="sm" onClick={handleAddUser} disabled={!newUserEmail || savingUser}>
                                                {savingUser ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add"}
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => {
                                                    setNewUserEmail(null);
                                                    setShowAddUser(false);
                                                }}
                                            >
                                                <X className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    )}

                                    {/* User List */}
                                    {loadingUsers ? (
                                        <div className="flex justify-center py-2">
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                        </div>
                                    ) : sharedUsers.length > 0 ? (
                                        <div className="max-h-32 space-y-1 overflow-y-auto">
                                            {sharedUsers.map(user => (
                                                <div key={user.user_email} className="group hover:bg-muted/50 flex items-center justify-between rounded px-2 py-1">
                                                    <div className="flex items-center gap-2">
                                                        <div className="bg-primary/10 text-primary flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium">{user.user_email.charAt(0).toUpperCase()}</div>
                                                        <span className="text-sm">{user.user_email}</span>
                                                    </div>
                                                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100" onClick={() => handleRemoveUser(user.user_email)} disabled={savingUser}>
                                                        <X className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            ))}
                                        </div>
                                    ) : !showAddUser ? (
                                        <p className="text-muted-foreground py-2 text-center text-xs">No specific people added</p>
                                    ) : null}
                                </div>

                                {/* Require Login Toggle - only show when no specific users are added */}
                                {/* When sharing with specific people, login is implicitly required */}
                                {sharedUsers.length === 0 && (
                                    <div className="flex items-center justify-between border-t pt-3">
                                        <div>
                                            <Label className="text-sm">Require login</Label>
                                            <p className="text-muted-foreground text-xs">Viewers must be logged in</p>
                                        </div>
                                        <Switch
                                            checked={requireAuth}
                                            onCheckedChange={checked => {
                                                setRequireAuth(checked);
                                                // Auto-save when toggled
                                                if (shareLink) {
                                                    updateShareLink(shareLink.share_id, { require_authentication: checked }).then(setShareLink).catch(console.error);
                                                }
                                            }}
                                            disabled={loading}
                                        />
                                    </div>
                                )}
                            </>
                        ) : (
                            /* Create Share Section */
                            <div className="space-y-4 py-4 text-center">
                                <div className="bg-muted/50 mx-auto flex h-16 w-16 items-center justify-center rounded-full">
                                    <Link className="text-muted-foreground h-8 w-8" />
                                </div>
                                <p className="font-medium">Create a share link</p>

                                <div className="flex items-center justify-center gap-2 text-sm">
                                    <Switch checked={requireAuth} onCheckedChange={setRequireAuth} />
                                    <Label className="cursor-pointer" onClick={() => setRequireAuth(!requireAuth)}>
                                        Require login to view
                                    </Label>
                                </div>
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        {!shareLink ? (
                            <Button onClick={handleCreateShare} disabled={loading} className="w-full">
                                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                Create Share Link
                            </Button>
                        ) : (
                            <Button variant="outline" onClick={() => onOpenChange(false)} className="w-full">
                                Done
                            </Button>
                        )}
                    </DialogFooter>
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
