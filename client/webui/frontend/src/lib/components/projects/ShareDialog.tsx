import { useState, useEffect, useCallback } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { Input } from "@/lib/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui/table";
import { Badge } from "@/lib/components/ui/badge";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { useProjectContext } from "@/lib/providers/ProjectProvider";
import { canShareProject } from "@/lib/utils/permissions";
import type { Project, ProjectRole, Collaborator } from "@/lib/types/projects";
import { Share2, Trash2, UserPlus, Users, Loader2 } from "lucide-react";

interface ShareDialogProps {
    project: Project;
    trigger?: React.ReactNode;
}

export function ShareDialog({ project, trigger }: ShareDialogProps) {
    const { getCollaborators, shareProject, updateCollaborator, removeCollaborator } = useProjectContext();

    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [shareLoading, setShareLoading] = useState(false);
    const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
    const [removingUserId, setRemovingUserId] = useState<string | null>(null);
    const [collaboratorToDelete, setCollaboratorToDelete] = useState<Collaborator | null>(null);
    const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
    const [email, setEmail] = useState("");
    const [role, setRole] = useState<ProjectRole>("viewer");
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Combined loading state for disabling buttons
    const isAnyOperationInProgress = loading || shareLoading || updatingUserId !== null || removingUserId !== null;

    // Permission check
    const isOwner = canShareProject(project);

    // Fetch collaborators when dialog opens
    const fetchCollaborators = useCallback(async () => {
        if (!project.id) return;

        try {
            setLoading(true);
            setError(null);
            const data = await getCollaborators(project.id);
            setCollaborators(data);
        } catch (err) {
            console.error("Failed to fetch collaborators:", err);
            setError("Failed to load collaborators. Please try again.");
        } finally {
            setLoading(false);
        }
    }, [project.id, getCollaborators]);

    useEffect(() => {
        if (open) {
            fetchCollaborators();
            // Reset state
            setEmail("");
            setRole("viewer");
            setError(null);
            setSuccess(null);
        }
    }, [open, fetchCollaborators]);

    const handleShare = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!email.trim()) return;

        try {
            setShareLoading(true);
            setError(null);
            setSuccess(null);

            await shareProject(project.id, email, role);

            // Refresh collaborators list to reflect the new addition
            await fetchCollaborators();
            setEmail("");
            setRole("viewer");
            setSuccess(`Invitation sent to ${email}`);

            // Clear success message after 3 seconds
            setTimeout(() => setSuccess(null), 3000);
        } catch (err) {
            console.error("Failed to share project:", err);
            setError(err instanceof Error ? err.message : "Failed to share project");
        } finally {
            setShareLoading(false);
        }
    };

    const handleUpdateRole = async (userId: string, newRole: ProjectRole) => {
        console.log("userId:", userId, "newRole:", newRole);
        console.log("projectId:", project.id);
        try {
            setUpdatingUserId(userId);
            setError(null);
            await updateCollaborator(project.id, userId, newRole);

            // Refresh collaborators list to reflect the updated role
            await fetchCollaborators();
        } catch (err) {
            console.error("Failed to update role:", err);
            setError("Failed to update collaborator role");
        } finally {
            setUpdatingUserId(null);
        }
    };

    const handleRemoveCollaborator = async () => {
        if (!collaboratorToDelete) return;

        try {
            setRemovingUserId(collaboratorToDelete.userId);
            setError(null);
            await removeCollaborator(project.id, collaboratorToDelete.userId);

            setCollaborators(prev => prev.filter(c => c.userId !== collaboratorToDelete.userId));
            setCollaboratorToDelete(null);
        } catch (err) {
            console.error("Failed to remove collaborator:", err);
            setError("Failed to remove collaborator");
        } finally {
            setRemovingUserId(null);
        }
    };

    // If user can't share, don't show the dialog/trigger at all?
    // Or maybe show it but in read-only mode?
    // For now, adhering to specs that say "Share button visible only to owners"
    if (!isOwner) return null;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                {trigger || (
                    <Button variant="outline" size="sm" className="gap-2">
                        <Share2 size={16} />
                        Share
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent className="sm:max-w-md md:max-w-lg">
                <DialogHeader>
                    <DialogTitle>Share Project</DialogTitle>
                    <DialogDescription>
                        Invite others to collaborate on <strong>{project.name}</strong>.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    {/* Status Messages */}
                    {error && <MessageBanner variant="error" message={error} dismissible onDismiss={() => setError(null)} />}
                    {success && <MessageBanner variant="success" message={success} dismissible onDismiss={() => setSuccess(null)} />}

                    {/* Invite Form */}
                    <form onSubmit={handleShare} className="flex items-end gap-2">
                        <div className="grid flex-1 gap-2">
                            <label htmlFor="email" className="text-sm font-medium">
                                Email address
                            </label>
                            <Input id="email" type="email" placeholder="colleague@example.com" value={email} onChange={e => setEmail(e.target.value)} required disabled={isAnyOperationInProgress} />
                        </div>
                        <div className="grid w-[110px] gap-2">
                            <label htmlFor="role" className="text-sm font-medium">
                                Role
                            </label>
                            <Select value={role} onValueChange={val => setRole(val as ProjectRole)} disabled={isAnyOperationInProgress}>
                                <SelectTrigger id="role">
                                    <SelectValue placeholder="Role" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="viewer">Viewer</SelectItem>
                                    <SelectItem value="editor">Editor</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <Button type="submit" disabled={isAnyOperationInProgress}>
                            {shareLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
                            <span className="sr-only">Invite</span>
                        </Button>
                    </form>

                    {/* Collaborators List */}
                    <div className="space-y-2">
                        <h4 className="flex items-center gap-2 text-sm font-medium">
                            <Users size={16} />
                            Collaborators
                        </h4>

                        <div className="max-h-[200px] overflow-y-auto rounded-md border">
                            {loading ? (
                                <div className="text-muted-foreground flex items-center justify-center p-8">
                                    <Loader2 className="mr-2 h-6 w-6 animate-spin" />
                                    Loading...
                                </div>
                            ) : collaborators.length === 0 ? (
                                <div className="text-muted-foreground p-8 text-center text-sm">No collaborators yet. Invite someone above!</div>
                            ) : (
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>User</TableHead>
                                            <TableHead className="w-[110px]">Role</TableHead>
                                            <TableHead className="w-[50px]"></TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {/* Show current user as Owner if they are the owner */}
                                        {/* Note: In a real app we might want to include the owner in the list from API,
                                            but typically the getCollaborators API returns people shared WITH.
                                            We'll rely on what the API returns. */}

                                        {collaborators.map(collaborator => (
                                            <TableRow key={collaborator.userId}>
                                                <TableCell className="font-medium">
                                                    <div className="flex flex-col">
                                                        <span>{collaborator.email || collaborator.userId}</span>
                                                        <span className="text-muted-foreground text-xs">Added {new Date(collaborator.addedAt).toLocaleDateString()}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    {collaborator.role === "owner" ? (
                                                        <Badge variant="secondary">Owner</Badge>
                                                    ) : (
                                                        <Select value={collaborator.role} onValueChange={val => handleUpdateRole(collaborator.userId, val as ProjectRole)} disabled={isAnyOperationInProgress}>
                                                            <SelectTrigger className="h-8 w-full">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                <SelectItem value="viewer">Viewer</SelectItem>
                                                                <SelectItem value="editor">Editor</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    {collaborator.role !== "owner" && (
                                                        <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive h-8 w-8" onClick={() => setCollaboratorToDelete(collaborator)} disabled={isAnyOperationInProgress}>
                                                            {removingUserId === collaborator.userId ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                                                            <span className="sr-only">Remove</span>
                                                        </Button>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            )}
                        </div>
                    </div>
                </div>
            </DialogContent>

            {/* Delete Confirmation Dialog */}
            <Dialog open={!!collaboratorToDelete} onOpenChange={isOpen => !isOpen && setCollaboratorToDelete(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Remove Collaborator</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to remove <strong>{collaboratorToDelete?.email || collaboratorToDelete?.userId}</strong> from this project? They will lose access immediately.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2 sm:gap-0">
                        <Button variant="outline" onClick={() => setCollaboratorToDelete(null)} disabled={removingUserId !== null}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleRemoveCollaborator} disabled={removingUserId !== null}>
                            {removingUserId ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Removing...
                                </>
                            ) : (
                                "Remove"
                            )}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Dialog>
    );
}
