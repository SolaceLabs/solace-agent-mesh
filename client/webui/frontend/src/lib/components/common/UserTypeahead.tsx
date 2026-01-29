/**
 * Inline typeahead component for searching and selecting users by email.
 * Uses Popover-based implementation with search input and dropdown results.
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import { X, Loader2 } from "lucide-react";
import { Input } from "@/lib/components/ui/input";
import { Button } from "@/lib/components/ui/button";
import { Badge } from "@/lib/components/ui/badge";
import { Popover, PopoverContent, PopoverAnchor } from "@/lib/components/ui/popover";
import { usePeopleSearch } from "@/lib/api/people";
import { useDebounce } from "@/lib/hooks/useDebounce";
import type { Person } from "@/lib/types";

interface UserTypeaheadProps {
    id: string;
    onSelect: (email: string, id: string) => void;
    onRemove: (id: string) => void;
    excludeEmails: string[];
    selectedEmail?: string | null;
    error?: boolean;
}

export const UserTypeahead: React.FC<UserTypeaheadProps> = ({ id, onSelect, onRemove, excludeEmails, selectedEmail, error }) => {
    const [searchQuery, setSearchQuery] = useState("");
    const [activeIndex, setActiveIndex] = useState(0);
    const [isKeyboardMode, setIsKeyboardMode] = useState(false);
    const [isOpen, setIsOpen] = useState(true);
    const inputRef = useRef<HTMLInputElement>(null);

    // Debounce search query
    const debouncedQuery = useDebounce(searchQuery, 200);

    // Fetch people using the hook
    const { data: searchResults, isLoading } = usePeopleSearch(debouncedQuery, {
        enabled: debouncedQuery.length > 0,
    });

    // Filter out already-added users
    const filteredPeople = (searchResults?.data || []).filter(person => !excludeEmails.includes(person.workEmail));

    // Focus input on mount
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    // Reset active index when results change
    useEffect(() => {
        setActiveIndex(0);
    }, [filteredPeople.length]);

    // Handle person selection - keep typeahead open
    const handleSelect = useCallback(
        (person: Person) => {
            onSelect(person.workEmail, id);
            setSearchQuery("");
        },
        [onSelect, id]
    );

    // Handle close/remove
    const handleClose = useCallback(() => {
        onRemove(id);
    }, [id, onRemove]);

    // Keyboard navigation
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Escape") {
                e.preventDefault();
                handleClose();
            } else if (e.key === "ArrowDown") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.min(prev + 1, filteredPeople.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.max(prev - 1, 0));
            } else if (e.key === "Enter") {
                e.preventDefault();
                if (filteredPeople.length > 0 && filteredPeople[activeIndex]) {
                    handleSelect(filteredPeople[activeIndex]);
                }
            }
        },
        [filteredPeople, activeIndex, handleSelect, handleClose]
    );

    // Scroll active item into view
    useEffect(() => {
        const activeElement = document.getElementById(`user-typeahead-${id}-item-${activeIndex}`);
        if (activeElement) {
            activeElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeIndex, id]);

    const showResults = searchQuery.length > 0 && !selectedEmail;

    // Handle input change - clear selection if user starts typing
    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const newValue = e.target.value;
            if (selectedEmail) {
                // Clear selection and start fresh search
                onSelect("", id);
                setSearchQuery(newValue);
            } else {
                setSearchQuery(newValue);
            }
        },
        [selectedEmail, onSelect, id]
    );

    return (
        <>
            <Popover open={isOpen && showResults} onOpenChange={setIsOpen}>
                <PopoverAnchor asChild>
                    <div className="relative">
                        <Input
                            ref={inputRef}
                            type="text"
                            placeholder="Search by email..."
                            value={selectedEmail || searchQuery}
                            onChange={handleInputChange}
                            onKeyDown={handleKeyDown}
                            onFocus={() => setIsOpen(true)}
                            className={`h-9 pr-9 ${error ? "border-[var(--destructive)]" : ""}`}
                        />
                        {isLoading && <Loader2 className="absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-[var(--muted-foreground)]" />}
                    </div>
                </PopoverAnchor>

                <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] min-w-[350px] p-0" onOpenAutoFocus={e => e.preventDefault()}>
                    <div className="max-h-[250px] overflow-y-auto">
                        {filteredPeople.length === 0 ? (
                            <div className="p-4 text-center text-sm text-[var(--muted-foreground)]">No users found</div>
                        ) : (
                            <div className="flex flex-col">
                                {filteredPeople.map((person, index) => (
                                    <button
                                        key={person.id}
                                        id={`user-typeahead-${id}-item-${index}`}
                                        onClick={() => handleSelect(person)}
                                        onMouseEnter={() => {
                                            setIsKeyboardMode(false);
                                            setActiveIndex(index);
                                        }}
                                        className={`w-full px-3 py-2 text-left transition-colors ${index === activeIndex ? "bg-[var(--accent)]" : !isKeyboardMode ? "hover:bg-[var(--accent)]" : ""}`}
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="min-w-0 flex-1">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="text-sm font-medium">{person.workEmail}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </PopoverContent>
            </Popover>
            <Badge variant="secondary" className="justify-self-center">
                Viewer
            </Badge>
            <Button variant="ghost" size="sm" onClick={handleClose} className="h-8 w-8 p-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                <X className="h-4 w-4" />
            </Button>
        </>
    );
};
