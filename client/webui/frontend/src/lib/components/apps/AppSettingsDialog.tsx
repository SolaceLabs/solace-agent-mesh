import { useState, useEffect, KeyboardEvent } from "react";
import { Loader2, Globe, Lock, X, Tag } from "lucide-react";

import { Button } from "../ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "../ui/dialog";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { Switch } from "../ui/switch";
import { Badge } from "../ui/badge";
import type { App } from "@/lib/types";

interface AppSettingsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    app: App;
    onSave: (updates: AppSettingsUpdate) => Promise<boolean>;
    onSaveTags?: (tags: string[]) => Promise<boolean>;
}

export interface AppSettingsUpdate {
    name?: string;
    description?: string;
    isPublic?: boolean;
}

export function AppSettingsDialog({ isOpen, onClose, app, onSave, onSaveTags }: AppSettingsDialogProps) {
    const [name, setName] = useState(app.name);
    const [description, setDescription] = useState(app.description || "");
    const [isPublic, setIsPublic] = useState(app.isPublic);
    const [tags, setTags] = useState<string[]>(app.tags || []);
    const [tagInput, setTagInput] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset form when dialog opens or app changes
    useEffect(() => {
        if (isOpen) {
            setName(app.name);
            setDescription(app.description || "");
            setIsPublic(app.isPublic);
            setTags(app.tags || []);
            setTagInput("");
            setError(null);
        }
    }, [isOpen, app]);

    const addTag = (tag: string) => {
        const normalizedTag = tag.toLowerCase().trim();
        if (normalizedTag && !tags.includes(normalizedTag)) {
            setTags([...tags, normalizedTag]);
        }
        setTagInput("");
    };

    const removeTag = (tagToRemove: string) => {
        setTags(tags.filter((t) => t !== tagToRemove));
    };

    const handleTagKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addTag(tagInput);
        } else if (e.key === "Backspace" && tagInput === "" && tags.length > 0) {
            removeTag(tags[tags.length - 1]);
        }
    };

    const tagsChanged = () => {
        const originalTags = app.tags || [];
        if (tags.length !== originalTags.length) return true;
        return tags.some((t) => !originalTags.includes(t));
    };

    const handleSave = async () => {
        if (!name.trim()) {
            setError("App name is required");
            return;
        }

        setSaving(true);
        setError(null);

        try {
            const updates: AppSettingsUpdate = {};

            // Only include changed fields
            if (name !== app.name) {
                updates.name = name.trim();
            }
            if (description !== (app.description || "")) {
                updates.description = description.trim();
            }
            if (isPublic !== app.isPublic) {
                updates.isPublic = isPublic;
            }

            let settingsSuccess = true;
            let tagsSuccess = true;

            // Save settings if there are changes
            if (Object.keys(updates).length > 0) {
                settingsSuccess = await onSave(updates);
            }

            // Save tags if they changed
            if (tagsChanged() && onSaveTags) {
                tagsSuccess = await onSaveTags(tags);
            }

            if (settingsSuccess && tagsSuccess) {
                onClose();
            } else {
                setError("Failed to save settings");
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to save settings");
        } finally {
            setSaving(false);
        }
    };

    const hasChanges =
        name !== app.name ||
        description !== (app.description || "") ||
        isPublic !== app.isPublic ||
        tagsChanged();

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>App Settings</DialogTitle>
                    <DialogDescription>
                        Configure your app's name, description, and visibility.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                    {/* General Section */}
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="app-name">Name</Label>
                            <Input
                                id="app-name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="App name"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="app-description">Description</Label>
                            <Textarea
                                id="app-description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="A brief description of your app"
                                rows={3}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="app-tags">Tags</Label>
                            <div className="flex flex-wrap gap-1.5 rounded-md border p-2 min-h-[42px]">
                                {tags.map((tag) => (
                                    <Badge
                                        key={tag}
                                        variant="secondary"
                                        className="gap-1 pr-1"
                                    >
                                        {tag}
                                        <button
                                            type="button"
                                            onClick={() => removeTag(tag)}
                                            className="ml-0.5 rounded-full p-0.5 hover:bg-muted"
                                        >
                                            <X className="size-3" />
                                        </button>
                                    </Badge>
                                ))}
                                <Input
                                    id="app-tags"
                                    value={tagInput}
                                    onChange={(e) => setTagInput(e.target.value)}
                                    onKeyDown={handleTagKeyDown}
                                    onBlur={() => tagInput && addTag(tagInput)}
                                    placeholder={tags.length === 0 ? "Add tags..." : ""}
                                    className="flex-1 min-w-[80px] border-0 p-0 h-6 focus-visible:ring-0 shadow-none"
                                />
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Press Enter or comma to add a tag
                            </p>
                        </div>
                    </div>

                    {/* Visibility Section */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <div className="h-px flex-1 bg-border" />
                            <span className="text-sm text-muted-foreground">Visibility</span>
                            <div className="h-px flex-1 bg-border" />
                        </div>

                        <div className="flex items-center justify-between rounded-lg border p-4">
                            <div className="flex items-center gap-3">
                                {isPublic ? (
                                    <Globe className="size-5 text-muted-foreground" />
                                ) : (
                                    <Lock className="size-5 text-muted-foreground" />
                                )}
                                <div>
                                    <div className="font-medium">
                                        {isPublic ? "Public" : "Private"}
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                        {isPublic
                                            ? "Anyone can see this app"
                                            : "Only you and collaborators can see this app"}
                                    </div>
                                </div>
                            </div>
                            <Switch
                                checked={isPublic}
                                onCheckedChange={setIsPublic}
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="text-sm text-destructive">{error}</div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={onClose} disabled={saving}>
                        Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={saving || !hasChanges}>
                        {saving ? (
                            <>
                                <Loader2 className="size-4 mr-2 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            "Save Changes"
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
