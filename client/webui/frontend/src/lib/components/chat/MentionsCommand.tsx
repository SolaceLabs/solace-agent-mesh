/**
 * Displays a popover with searchable people list when "@" is typed
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Search, User, Clock } from "lucide-react";
import type { Person, PeopleSearchResponse } from "@/lib/types";
import { api } from "@/lib/api";
import { getRecentMentions } from "@/lib/utils/recentMentions";

interface MentionsCommandProps {
    isOpen: boolean;
    onClose: () => void;
    textAreaRef: React.RefObject<HTMLDivElement | HTMLTextAreaElement | null>;
    onPersonSelect: (person: Person) => void;
    searchQuery: string;
}

export const MentionsCommand: React.FC<MentionsCommandProps> = ({ isOpen, onClose, textAreaRef, onPersonSelect, searchQuery }) => {
    const [activeIndex, setActiveIndex] = useState(0);
    const [people, setPeople] = useState<Person[]>([]);
    const [recentMentions, setRecentMentions] = useState<Person[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isKeyboardMode, setIsKeyboardMode] = useState(false);
    const [showingRecent, setShowingRecent] = useState(false);
    const [popupPosition, setPopupPosition] = useState<{ top: number; left: number } | null>(null);

    const popoverRef = useRef<HTMLDivElement>(null);
    const backdropRef = useRef<HTMLDivElement>(null);
    const prevPeopleCountRef = useRef<number>(0);

    // Calculate popup position based on cursor location
    useEffect(() => {
        if (isOpen && textAreaRef.current) {
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();

                // Popup dimensions
                const popupWidth = 400;
                const popupHeight = 300; // max height

                // Viewport dimensions
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;

                // Calculate available space
                const spaceBelow = viewportHeight - rect.bottom;
                const spaceAbove = rect.top;
                const spaceRight = viewportWidth - rect.left;

                // Decide vertical position (above or below cursor)
                let top: number;
                if (spaceBelow >= popupHeight || spaceBelow > spaceAbove) {
                    // Position below cursor
                    top = rect.bottom + 8;
                } else {
                    // Position above cursor
                    top = rect.top - popupHeight - 8;
                }

                // Decide horizontal position (align with cursor, but adjust if too close to right edge)
                let left: number;
                if (spaceRight >= popupWidth) {
                    // Enough space on the right, align with cursor
                    left = rect.left;
                } else {
                    // Not enough space, shift left
                    left = viewportWidth - popupWidth - 16; // 16px margin from edge
                }

                // Ensure we don't go off the left edge
                left = Math.max(16, left);

                // Ensure we don't go off the top
                top = Math.max(16, top);

                setPopupPosition({ top, left });
            }
        }
    }, [isOpen, textAreaRef]);

    // Load recent mentions when popup opens
    useEffect(() => {
        if (isOpen) {
            const recent = getRecentMentions();
            setRecentMentions(recent);
        }
    }, [isOpen]);

    // Fetch people when search query changes (debounced)
    useEffect(() => {
        if (!isOpen) return;

        // If no search query, show recent mentions
        if (searchQuery.length === 0) {
            setPeople([]);
            setShowingRecent(true);
            setIsLoading(false);
            return;
        }

        // If 1+ characters, do backend search
        setShowingRecent(false);

        const fetchPeople = async () => {
            setIsLoading(true);
            try {
                const data: PeopleSearchResponse = await api.webui.get(`/api/v1/people/search?q=${encodeURIComponent(searchQuery)}&limit=10`);
                setPeople(data.data || []);
            } catch (error) {
                console.error("Failed to fetch people:", error);
                setPeople([]);
            } finally {
                setIsLoading(false);
            }
        };

        // Debounce API calls by 200ms
        const timeoutId = setTimeout(fetchPeople, 200);
        return () => clearTimeout(timeoutId);
    }, [isOpen, searchQuery]);

    // Handle person selection
    const handlePersonSelect = useCallback(
        (person: Person) => {
            onPersonSelect(person);
            onClose();
        },
        [onPersonSelect, onClose]
    );

    // Keyboard navigation - handle at window level so textarea stays focused
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            const currentList = showingRecent ? recentMentions : people;

            if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                onClose();
                textAreaRef.current?.focus();
            } else if (e.key === "ArrowDown") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.min(prev + 1, currentList.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIsKeyboardMode(true);
                setActiveIndex(prev => Math.max(prev - 1, 0));
            } else if (e.key === "Enter" || e.key === "Tab") {
                if (currentList.length > 0 && currentList[activeIndex]) {
                    e.preventDefault();
                    handlePersonSelect(currentList[activeIndex]);
                }
            }
        };

        // Add event listener to window for keyboard navigation
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, people, recentMentions, showingRecent, activeIndex, handlePersonSelect, onClose, textAreaRef]);

    // Reset active index when popup opens or when the list changes
    useEffect(() => {
        setActiveIndex(0);
    }, [isOpen, showingRecent]);

    // Reset active index when people list changes (from search)
    // Only reset if the count actually changed to avoid resetting during arrow key navigation
    useEffect(() => {
        if (!showingRecent && people.length > 0 && people.length !== prevPeopleCountRef.current) {
            setActiveIndex(0);
            prevPeopleCountRef.current = people.length;
        }
    }, [people, showingRecent]);

    // Scroll active item into view
    useEffect(() => {
        const activeElement = document.getElementById(`person-item-${activeIndex}`);
        if (activeElement) {
            activeElement.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }, [activeIndex]);

    if (!isOpen || !popupPosition) return null;

    return (
        <>
            {/* Backdrop */}
            <div ref={backdropRef} className="fixed inset-0 z-40 bg-transparent" onClick={onClose} />

            <div
                className="fixed z-50 w-[400px]"
                style={{
                    top: `${popupPosition.top}px`,
                    left: `${popupPosition.left}px`,
                }}
            >
                <div ref={popoverRef} className="flex flex-col rounded-lg border border-[var(--border)] bg-[var(--background)] shadow-lg" style={{ maxHeight: "300px" }}>
                    {/* Search Display */}
                    <div className="flex items-center gap-2 border-b border-[var(--border)] p-3">
                        {showingRecent ? (
                            <>
                                <Clock className="size-4 text-[var(--muted-foreground)]" />
                                <div className="flex-1 text-sm text-[var(--muted-foreground)]">
                                    <span>Recent mentions</span>
                                </div>
                            </>
                        ) : (
                            <>
                                <Search className="size-4 text-[var(--muted-foreground)]" />
                                <div className="flex-1 text-sm text-[var(--muted-foreground)]">
                                    <span>
                                        Searching for: <strong>{searchQuery}</strong>
                                    </span>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Results List */}
                    <div className="min-h-0 flex-1 overflow-y-auto">
                        {isLoading ? (
                            <div className="flex items-center justify-center p-8">
                                <div className="size-6 animate-spin rounded-full border-2 border-[var(--primary)] border-t-transparent" />
                            </div>
                        ) : showingRecent && recentMentions.length === 0 ? (
                            <div className="flex flex-col items-center justify-center gap-4 p-8 text-center">
                                <p className="text-sm text-[var(--muted-foreground)]">No recent mentions. Start typing to search...</p>
                            </div>
                        ) : showingRecent ? (
                            <div className="flex flex-col p-2">
                                {recentMentions.map((person, index) => {
                                    return (
                                        <button
                                            key={person.id}
                                            id={`person-item-${index}`}
                                            onClick={() => handlePersonSelect(person)}
                                            onMouseEnter={() => {
                                                setIsKeyboardMode(false);
                                                setActiveIndex(index);
                                            }}
                                            className={`w-full rounded-md p-3 text-left transition-colors ${index === activeIndex ? "bg-[var(--accent)]" : !isKeyboardMode ? "hover:bg-[var(--accent)]" : ""}`}
                                        >
                                            <div className="flex items-start gap-3">
                                                <Clock className="mt-0.5 size-4 flex-shrink-0 text-[var(--muted-foreground)]" />
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <span className="text-sm font-medium">{person.displayName}</span>
                                                        {person.jobTitle && <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-xs text-[var(--muted-foreground)]">{person.jobTitle}</span>}
                                                    </div>
                                                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">{person.workEmail}</p>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        ) : people.length === 0 ? (
                            <div className="flex flex-col items-center justify-center gap-4 p-8 text-center">
                                <p className="text-sm text-[var(--muted-foreground)]">No people found matching "{searchQuery}"</p>
                            </div>
                        ) : (
                            <div className="flex flex-col p-2">
                                {people.map((person, index) => {
                                    return (
                                        <button
                                            key={person.id}
                                            id={`person-item-${index}`}
                                            onClick={() => handlePersonSelect(person)}
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
                                                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">{person.workEmail}</p>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </>
    );
};
