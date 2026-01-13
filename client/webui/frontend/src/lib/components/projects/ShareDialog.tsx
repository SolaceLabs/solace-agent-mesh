import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";
import { Input } from "@/lib/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/lib/components/ui/table";
import { Badge } from "@/lib/components/ui/badge";
import { Switch } from "@/lib/components/ui/switch";
import { Popover, PopoverContent, PopoverAnchor } from "@/lib/components/ui/popover";
import { MessageBanner } from "@/lib/components/common/MessageBanner";
import { canShareProject } from "@/lib/utils/permissions";
import type { Project, ProjectRole, Collaborator } from "@/lib/types/projects";
import { Share2, Trash2, UserPlus, Users, Loader2, Search } from "lucide-react";
import { useCollaborators, useShareProject, useUpdateCollaborator, useRemoveCollaborator } from "@/lib/api/projects/hooks";
import { useSearchPeople } from "@/lib/api/people/hooks";
import { useDebounce } from "@/lib/hooks/useDebounce";

interface ShareDialogProps {
    project: Project;
    trigger?: React.ReactNode;
}

export function ShareDialog({ project, trigger }: ShareDialogProps) {
    const [open, setOpen] = useState(false);
    const [collaboratorToDelete, setCollaboratorToDelete] = useState<Collaborator | null>(null);
    const [email, setEmail] = useState("");
    const [role, setRole] = useState<ProjectRole>("viewer");
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [useTypeahead, setUseTypeahead] = useState(false);

    // Typeahead search state
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const [popoverOpen, setPopoverOpen] = useState(false);

    // Debounce search query (300ms delay)
    const debouncedSearchQuery = useDebounce(searchQuery, 300);

    // React Query hooks
    const { data: collaborators = [], isLoading: loading } = useCollaborators(open ? project.id : null);
    const shareProjectMutation = useShareProject();
    const updateCollaboratorMutation = useUpdateCollaborator();
    const removeCollaboratorMutation = useRemoveCollaborator();

    // Search people hook (only trigger if query is 2+ characters and in typeahead mode)
    const shouldSearch = debouncedSearchQuery.length >= 2 && useTypeahead && open;
    const { data: searchData, isLoading: isSearching } = useSearchPeople(shouldSearch ? debouncedSearchQuery : null, 10, shouldSearch);
    const searchResults = searchData?.data || [];

    // Combined loading state for disabling buttons
    const isAnyOperationInProgress = loading || shareProjectMutation.isPending || updateCollaboratorMutation.isPending || removeCollaboratorMutation.isPending;

    // Permission check
    const isOwner = canShareProject(project);

    // Reset form state when dialog opens
    useEffect(() => {
        if (open) {
            setEmail("");
            setRole("viewer");
            setError(null);
            setSuccess(null);
            setUseTypeahead(false);
            setSearchQuery("");
            setSelectedIndex(-1);
            setPopoverOpen(false);
        }
    }, [open]);

    // Handle mode toggle change
    const handleModeToggle = (checked: boolean) => {
        setUseTypeahead(checked);
        // Clear state when switching modes
        setEmail("");
        setError(null);
        setSuccess(null);
        setSearchQuery("");
        setSelectedIndex(-1);
        setPopoverOpen(false);
    };

    const handleShare = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!email.trim()) return;

        setError(null);
        setSuccess(null);

        shareProjectMutation.mutate(
            { projectId: project.id, email, role },
            {
                onSuccess: () => {
                    setEmail("");
                    setRole("viewer");
                    setSuccess(`Invitation sent to ${email}`);

                    // Clear success message after 3 seconds
                    setTimeout(() => setSuccess(null), 3000);
                },
                onError: err => {
                    console.error("Failed to share project:", err);
                    setError(err instanceof Error ? err.message : "Failed to share project");
                },
            }
        );
    };

    const handleUpdateRole = async (userId: string, newRole: ProjectRole) => {
        console.log("userId:", userId, "newRole:", newRole);
        console.log("projectId:", project.id);

        setError(null);

        updateCollaboratorMutation.mutate(
            { projectId: project.id, userId, role: newRole },
            {
                onError: err => {
                    console.error("Failed to update role:", err);
                    setError("Failed to update collaborator role");
                },
            }
        );
    };

    const handleRemoveCollaborator = async () => {
        if (!collaboratorToDelete) return;

        setError(null);

        removeCollaboratorMutation.mutate(
            { projectId: project.id, userId: collaboratorToDelete.userId },
            {
                onSuccess: () => {
                    setCollaboratorToDelete(null);
                },
                onError: err => {
                    console.error("Failed to remove collaborator:", err);
                    setError("Failed to remove collaborator");
                },
            }
        );
    };

    // Handle keyboard navigation in search results
    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!popoverOpen || searchResults.length === 0) {
            if (e.key === "Escape") {
                setSearchQuery("");
                setSelectedIndex(-1);
                setPopoverOpen(false);
            }
            return;
        }

        switch (e.key) {
            case "ArrowDown":
                e.preventDefault();
                setSelectedIndex(prev => (prev < searchResults.length - 1 ? prev + 1 : prev));
                break;
            case "ArrowUp":
                e.preventDefault();
                setSelectedIndex(prev => (prev > 0 ? prev - 1 : -1));
                break;
            case "Enter":
                e.preventDefault();
                if (selectedIndex >= 0 && selectedIndex < searchResults.length) {
                    // TODO: Add selected user to pending list (next task)
                    console.log("Selected user:", searchResults[selectedIndex]);
                }
                break;
            case "Escape":
                e.preventDefault();
                setSearchQuery("");
                setSelectedIndex(-1);
                setPopoverOpen(false);
                break;
        }
    };

    // Update popover open state based on search results
    useEffect(() => {
        if (searchQuery.length >= 2 && useTypeahead) {
            setPopoverOpen(true);
        } else {
            setPopoverOpen(false);
            setSelectedIndex(-1);
        }
    }, [searchQuery, useTypeahead]);

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

                    {/* Mode Toggle */}
                    <div className="flex items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                            <div className="text-sm font-medium">{useTypeahead ? "Search Users" : "Manual Email Entry"}</div>
                            <p className="text-muted-foreground text-xs">{useTypeahead ? "Search and select users from the directory" : "Invite users by entering their email address"}</p>
                        </div>
                        <Switch checked={useTypeahead} onCheckedChange={handleModeToggle} disabled={isAnyOperationInProgress} />
                    </div>

                    {/* Invite Form - Only show in email mode */}
                    {!useTypeahead && (
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
                                {shareProjectMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
                                <span className="sr-only">Invite</span>
                            </Button>
                        </form>
                    )}

                    {/* Typeahead Search - Only show in typeahead mode */}
                    {useTypeahead && (
                        <div className="space-y-2">
                            <label htmlFor="search" className="text-sm font-medium">
                                Search for users
                            </label>
                            <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
                                <PopoverAnchor asChild>
                                    <div className="relative">
                                        <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                                        <Input
                                            id="search"
                                            type="text"
                                            placeholder="Search by name or email..."
                                            value={searchQuery}
                                            onChange={e => setSearchQuery(e.target.value)}
                                            onKeyDown={handleSearchKeyDown}
                                            className="pr-9 pl-9"
                                            disabled={isAnyOperationInProgress}
                                        />
                                        {isSearching && <Loader2 className="text-muted-foreground absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 animate-spin" />}
                                    </div>
                                </PopoverAnchor>
                                <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-0" onOpenAutoFocus={e => e.preventDefault()}>
                                    {searchResults.length > 0 ? (
                                        <div className="max-h-[300px] overflow-y-auto">
                                            {searchResults.map((user, index) => (
                                                <button
                                                    key={user.id}
                                                    type="button"
                                                    className={`hover:bg-accent flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm ${index === selectedIndex ? "bg-accent" : ""}`}
                                                    onClick={() => {
                                                        // TODO: Add selected user to pending list (next task)
                                                        console.log("Clicked user:", user);
                                                    }}
                                                    onMouseEnter={() => setSelectedIndex(index)}
                                                >
                                                    <div className="font-medium">{user.name}</div>
                                                    <div className="text-muted-foreground flex items-center gap-2 text-xs">
                                                        <span>{user.email}</span>
                                                        {user.title && (
                                                            <>
                                                                <span>•</span>
                                                                <span>{user.title}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    ) : debouncedSearchQuery.length >= 2 && !isSearching ? (
                                        <div className="text-muted-foreground px-3 py-6 text-center text-sm">No users found</div>
                                    ) : null}
                                </PopoverContent>
                            </Popover>
                        </div>
                    )}

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
                                                            <Trash2 className="h-4 w-4" />
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
                        <Button variant="outline" onClick={() => setCollaboratorToDelete(null)} disabled={removeCollaboratorMutation.isPending}>
                            Cancel
                        </Button>
                        <Button variant="destructive" onClick={handleRemoveCollaborator} disabled={removeCollaboratorMutation.isPending}>
                            {removeCollaboratorMutation.isPending ? (
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
