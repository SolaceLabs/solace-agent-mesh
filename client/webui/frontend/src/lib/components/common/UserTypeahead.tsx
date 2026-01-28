/**
 * Reusable typeahead component for searching and selecting users by email
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Search, User } from "lucide-react";
import { Input } from "@/lib/components/ui/input";
import { PopoverManual } from "@/lib/components/ui/popoverManual";
import { usePeopleSearch } from "@/lib/api/people";
import type { Person } from "@/lib/types";

interface UserTypeaheadProps {
    onSelect: (email: string) => void;
    excludeEmails: string[];
    onClose: () => void;
    anchorRef: React.RefObject<HTMLElement | null>;
}

export const UserTypeahead: React.FC<UserTypeaheadProps> = ({ onSelect, excludeEmails, onClose, anchorRef }) => {
    const [searchQuery, setSearchQuery] = useState("");
    const [debouncedQuery, setDebouncedQuery] = useState("");
    const [activeIndex, setActiveIndex] = useState(0);
    const [isKeyboardMode, setIsKeyboardMode] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    // Debounce search query
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            setDebouncedQuery(searchQuery);
        }, 200);
        return () => clearTimeout(timeoutId);
    }, [searchQuery]);

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

    // Handle person selection
    const handleSelect = useCallback(
        (person: Person) => {
            onSelect(person.workEmail);
            onClose();
        },
        [onSelect, onClose]
    );

    // Keyboard navigation
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "Escape") {
                e.preventDefault();
                onClose();
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
        [filteredPeople, activeIndex, handleSelect, onClose]
    );

    // Scroll active item into view
    useEffect(() => {
        const activeElement = document.getElementById(`user-typeahead-item-${activeIndex}`);
        if (activeElement) {
            activeElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeIndex]);

    return (
        <PopoverManual isOpen={true} onClose={onClose} anchorRef={anchorRef} placement="bottom-start" className="w-[350px] rounded-lg">
            <div className="flex flex-col">
                {/* Search Input */}
                <div className="border-b border-[var(--border)] p-3">
                    <div className="flex items-center gap-2">
                        <Search className="size-4 text-[var(--muted-foreground)]" />
                        <Input ref={inputRef} type="text" placeholder="Search by email..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} onKeyDown={handleKeyDown} className="h-8 border-0 p-0 shadow-none focus-visible:ring-0" />
                    </div>
                </div>

                {/* Results List */}
                <div className="max-h-[250px] overflow-y-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center p-6">
                            <div className="size-5 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                        </div>
                    ) : searchQuery.length === 0 ? (
                        <div className="p-6 text-center text-sm text-[var(--muted-foreground)]">Type to search for users...</div>
                    ) : filteredPeople.length === 0 ? (
                        <div className="p-6 text-center text-sm text-[var(--muted-foreground)]">No users found</div>
                    ) : (
                        <div className="flex flex-col p-2">
                            {filteredPeople.map((person, index) => (
                                <button
                                    key={person.id}
                                    id={`user-typeahead-item-${index}`}
                                    onClick={() => handleSelect(person)}
                                    onMouseEnter={() => {
                                        setIsKeyboardMode(false);
                                        setActiveIndex(index);
                                    }}
                                    className={`w-full rounded-md p-3 text-left transition-colors ${index === activeIndex ? "bg-[var(--accent)]" : !isKeyboardMode ? "hover:bg-[var(--accent)]" : ""}`}
                                >
                                    <div className="flex items-start gap-3">
                                        <User className="mt-0.5 size-4 flex-shrink-0 text-[var(--muted-foreground)]" />
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span className="text-sm font-medium">{person.displayName}</span>
                                                {person.jobTitle && <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">{person.jobTitle}</span>}
                                            </div>
                                            <p className="mt-1 truncate text-xs text-[var(--muted-foreground)]">{person.workEmail}</p>
                                        </div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </PopoverManual>
    );
};
