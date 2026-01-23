/**
 * ShareDialog component - Modal for managing share links
 *
 * NOTE: This component uses console.log for notifications.
 * TODO: Integrate with SAM's notification system (addToast, showNotification, etc.)
 */

import { useState, useEffect } from "react";
import { Copy, Check, X, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { Badge } from "../ui/badge";
import { ConfirmationDialog } from "../common/ConfirmationDialog";
import { ErrorLabel } from "../common/ErrorLabel";
import { createShareLink, getShareLinkForSession, updateShareLink, deleteShareLink, copyToClipboard, getAccessTypeDisplay } from "../../api/shareApi";
import type { ShareLink } from "../../types/share";

// Simple domain validation
const isValidDomain = (domain: string): boolean => {
    // Domain must contain at least one dot, no spaces, and be alphanumeric with dots/hyphens
    const domainRegex = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/i;
    return domainRegex.test(domain);
};

// Simple notification helper - replace with SAM's notification system
const showNotification = (message: string, type: "success" | "error" = "success") => {
    console.log(`[${type.toUpperCase()}]`, message);
    // TODO: Replace with SAM's actual notification system
    // Example: addToast({ message, type });
};

interface ShareDialogProps {
    sessionId: string;
    sessionTitle: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ShareDialog({ sessionId, sessionTitle, open, onOpenChange }: ShareDialogProps) {
    const [shareLink, setShareLink] = useState<ShareLink | null>(null);
    const [loading, setLoading] = useState(false);
    const [copied, setCopied] = useState(false);
    const [requireAuth, setRequireAuth] = useState(false);
    const [domains, setDomains] = useState<string[]>([]);
    const [domainInput, setDomainInput] = useState("");
    const [domainError, setDomainError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // Load existing share link when dialog opens
    useEffect(() => {
        if (open) {
            loadShareLink();
        }
    }, [open, sessionId]);

    const loadShareLink = async () => {
        setLoading(true);
        try {
            const link = await getShareLinkForSession(sessionId);
            if (link) {
                setShareLink(link);
                setRequireAuth(link.require_authentication);
                setDomains(link.allowed_domains || []);
            }
        } catch (error) {
            console.error("Failed to load share link:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateShare = async () => {
        setLoading(true);
        try {
            const link = await createShareLink(sessionId, {
                require_authentication: requireAuth,
                allowed_domains: domains.length > 0 ? domains : undefined,
            });
            setShareLink(link);
            showNotification("Share link created - Your session is now shared", "success");
        } catch (error) {
            showNotification(`Failed to create share link: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateShare = async () => {
        if (!shareLink) return;

        setLoading(true);
        try {
            const updated = await updateShareLink(shareLink.share_id, {
                require_authentication: requireAuth,
                allowed_domains: domains.length > 0 ? domains : undefined,
            });
            setShareLink(updated);
            showNotification("Share link updated - Settings have been saved", "success");
        } catch (error) {
            showNotification(`Failed to update share link: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
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
            setDomains([]);
            setShowDeleteConfirm(false);
            showNotification("Share link deleted - The share link has been removed", "success");
        } catch (error) {
            showNotification(`Failed to delete share link: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const handleCopyUrl = async () => {
        if (!shareLink) return;

        const success = await copyToClipboard(shareLink.share_url);
        if (success) {
            setCopied(true);
            showNotification("Copied to clipboard - Share URL has been copied", "success");
            setTimeout(() => setCopied(false), 2000);
        } else {
            showNotification("Failed to copy - Please copy the URL manually", "error");
        }
    };

    const handleAddDomain = () => {
        const domain = domainInput.trim().toLowerCase();
        setDomainError(null);

        if (!domain) {
            setDomainError("Please enter a domain");
            return;
        }

        if (!isValidDomain(domain)) {
            setDomainError("Please enter a valid domain (e.g., company.com)");
            return;
        }

        if (domains.includes(domain)) {
            setDomainError("This domain has already been added");
            return;
        }

        setDomains([...domains, domain]);
        setDomainInput("");
    };

    const handleRemoveDomain = (domain: string) => {
        setDomains(domains.filter(d => d !== domain));
    };

    const accessTypeInfo = shareLink ? getAccessTypeDisplay(shareLink.access_type) : null;

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                        <DialogTitle>Share "{sessionTitle}"</DialogTitle>
                        <DialogDescription>{shareLink ? "Manage your share link settings" : "Create a share link to share this session with others"}</DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        {/* Access Type Badge */}
                        {shareLink && accessTypeInfo && (
                            <div className="flex items-center gap-2">
                                <Badge variant="secondary" className="text-sm">
                                    {accessTypeInfo.icon} {accessTypeInfo.label}
                                </Badge>
                                <span className="text-muted-foreground text-xs">{accessTypeInfo.description}</span>
                            </div>
                        )}

                        {/* Share URL */}
                        {shareLink && (
                            <div className="space-y-2">
                                <Label>Share URL</Label>
                                <div className="flex gap-2">
                                    <Input value={shareLink.share_url} readOnly className="flex-1" />
                                    <Button variant="outline" size="icon" onClick={handleCopyUrl} disabled={loading}>
                                        {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Authentication Toggle */}
                        <div className="flex items-center justify-between space-x-2">
                            <div className="space-y-0.5">
                                <Label>Require Authentication</Label>
                                <p className="text-muted-foreground text-sm">Only logged-in users can view this session</p>
                            </div>
                            <Switch checked={requireAuth} onCheckedChange={setRequireAuth} disabled={loading} />
                        </div>

                        {/* Domain Restriction */}
                        {requireAuth && (
                            <div className="space-y-2">
                                <Label>Restrict to Email Domains (Optional)</Label>
                                <p className="text-muted-foreground text-sm">Only users with these email domains can access</p>

                                {/* Domain Tags */}
                                {domains.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {domains.map(domain => (
                                            <Badge key={domain} variant="outline" className="gap-1">
                                                {domain}
                                                <button onClick={() => handleRemoveDomain(domain)} className="hover:text-destructive ml-1" disabled={loading}>
                                                    <X className="h-3 w-3" />
                                                </button>
                                            </Badge>
                                        ))}
                                    </div>
                                )}

                                {/* Add Domain Input */}
                                <div className="space-y-1">
                                    <div className="flex gap-2">
                                        <Input
                                            placeholder="company.com"
                                            value={domainInput}
                                            onChange={e => {
                                                setDomainInput(e.target.value);
                                                setDomainError(null);
                                            }}
                                            onKeyPress={e => {
                                                if (e.key === "Enter") {
                                                    e.preventDefault();
                                                    handleAddDomain();
                                                }
                                            }}
                                            disabled={loading}
                                            className={domainError ? "border-red-500" : ""}
                                        />
                                        <Button onClick={handleAddDomain} variant="outline" disabled={loading}>
                                            Add
                                        </Button>
                                    </div>
                                    <ErrorLabel message={domainError ?? undefined} />
                                </div>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="flex justify-between sm:justify-between">
                        <div>
                            {shareLink && (
                                <Button variant="ghost" size="sm" onClick={() => setShowDeleteConfirm(true)} disabled={loading}>
                                    Delete
                                </Button>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
                                Close
                            </Button>
                            <Button onClick={shareLink ? handleUpdateShare : handleCreateShare} disabled={loading}>
                                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                {shareLink ? "Update" : "Create"} Share Link
                            </Button>
                        </div>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <ConfirmationDialog
                open={showDeleteConfirm}
                onOpenChange={open => !open && setShowDeleteConfirm(false)}
                title="Delete Share Link"
                content={<>This action cannot be undone. Anyone with the link will no longer be able to access this session.</>}
                actionLabels={{ confirm: "Delete" }}
                onConfirm={handleDeleteShare}
                onCancel={() => setShowDeleteConfirm(false)}
                isLoading={loading}
            />
        </>
    );
}
