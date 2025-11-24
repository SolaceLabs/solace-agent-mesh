import React, { useState } from "react";
import { Bookmark, Plus, X, Trash2 } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/lib/components/ui/popover";
import { Input } from "@/lib/components/ui/input";
import { useSessionTagContext } from "@/lib/providers/SessionTagProvider";

interface BookmarkNavProps {
    selectedTags: string[];
    onTagsChange: (tags: string[]) => void;
}

export const BookmarkNav: React.FC<BookmarkNavProps> = ({ selectedTags, onTagsChange }) => {
    const { tags, createTag, deleteTag } = useSessionTagContext();
    const [isOpen, setIsOpen] = useState(false);
    const [newTagName, setNewTagName] = useState("");
    const [isCreating, setIsCreating] = useState(false);

    const handleTagToggle = (tag: string) => {
        if (selectedTags.includes(tag)) {
            onTagsChange(selectedTags.filter(t => t !== tag));
        } else {
            onTagsChange([...selectedTags, tag]);
        }
    };

    const handleCreateTag = async (e?: React.MouseEvent) => {
        e?.preventDefault();
        e?.stopPropagation();

        if (!newTagName.trim()) return;

        setIsCreating(true);
        try {
            const result = await createTag({ tag: newTagName.trim() });
            if (result) {
                setNewTagName("");
                console.log("Created tag:", result);
            }
        } catch (error) {
            console.error("Failed to create tag:", error);
        } finally {
            setIsCreating(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleCreateTag();
        }
    };

    const handleDeleteTag = async (tag: string) => {
        await deleteTag(tag);
        // Remove from selected tags if it was selected
        if (selectedTags.includes(tag)) {
            onTagsChange(selectedTags.filter(t => t !== tag));
        }
    };

    const availableTags = tags.filter(tag => tag.count >= 0); // Show all tags, not just those with count > 0

    return (
        <Popover open={isOpen} onOpenChange={setIsOpen}>
            <PopoverTrigger asChild>
                <Button variant="ghost" className="h-10 justify-start text-sm font-normal" tooltip="Filter by bookmark">
                    {selectedTags.length > 0 ? <Bookmark className="mr-2 size-5 fill-current" /> : <Bookmark className="mr-2 size-5" />}
                    <span className="flex-1 truncate text-left">{selectedTags.length > 0 ? selectedTags.join(", ") : "Bookmarks"}</span>
                </Button>
            </PopoverTrigger>

            <PopoverContent className="w-64 p-2" align="start">
                <div className="space-y-2">
                    {/* Clear all button */}
                    {selectedTags.length > 0 && (
                        <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs" onClick={() => onTagsChange([])}>
                            <X className="h-3 w-3" />
                            Clear All
                        </Button>
                    )}

                    {/* Existing tags */}
                    {availableTags.length > 0 && (
                        <>
                            {selectedTags.length > 0 && <div className="border-t" />}
                            <div className="space-y-1">
                                {availableTags.map(tag => (
                                    <div key={tag.id} className="flex items-center justify-between">
                                        <Button variant="ghost" size="sm" className="flex-1 justify-start gap-2 text-xs" onClick={() => handleTagToggle(tag.tag)}>
                                            {selectedTags.includes(tag.tag) ? <Bookmark className="h-3 w-3 fill-current" /> : <Bookmark className="h-3 w-3" />}
                                            <span className="truncate">{tag.tag}</span>
                                            <span className="text-muted-foreground">({tag.count})</span>
                                        </Button>
                                        <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => handleDeleteTag(tag.tag)}>
                                            <Trash2 className="h-3 w-3" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}

                    {/* Create new tag */}
                    <div className="border-t pt-2">
                        <div className="flex gap-2">
                            <Input placeholder="New bookmark..." value={newTagName} onChange={e => setNewTagName(e.target.value)} onKeyDown={handleKeyDown} className="h-8 text-xs" />
                            <Button size="sm" onClick={handleCreateTag} disabled={!newTagName.trim() || isCreating} className="h-8 w-8 p-0" type="button">
                                <Plus className="h-3 w-3" />
                            </Button>
                        </div>
                    </div>

                    {/* No bookmarks message */}
                    {availableTags.length === 0 && <div className="text-muted-foreground py-4 text-center text-xs">No bookmarks yet</div>}
                </div>
            </PopoverContent>
        </Popover>
    );
};
