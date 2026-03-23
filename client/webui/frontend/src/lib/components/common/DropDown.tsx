import { useState, useRef, useEffect } from "react";
import type { ReactNode } from "react";
import { Check, ChevronDown, Loader2 } from "lucide-react";

import { Input } from "@/lib/components/ui";

export interface DropDownItem {
    id: string;
    label: string;
    icon?: ReactNode;
    subtext?: string;
    section?: "default" | "advanced";
}

interface DropDownProps {
    value: string | undefined;
    onValueChange: (value: string) => void;
    items: DropDownItem[];
    placeholder?: string;
    disabled?: boolean;
    invalid?: boolean;
    isLoading?: boolean;
    renderItem?: (item: DropDownItem) => ReactNode;
    onOpen?: () => void;
}

export const DropDown = ({ value, onValueChange, items, placeholder = "Select an option...", disabled, invalid, isLoading, renderItem, onOpen }: DropDownProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [searchText, setSearchText] = useState("");
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const [openAbove, setOpenAbove] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const focusByMouseRef = useRef(false);

    const selectedItem = items.find(item => item.id === value);

    // Filter items based on search text
    const filteredItems = searchText ? items.filter(item => item.label.toLowerCase().includes(searchText.toLowerCase()) || item.id.toLowerCase().includes(searchText.toLowerCase())) : items;

    // If user typed something that doesn't match any items, add it as a custom option
    let itemsToDisplay = filteredItems;
    if (searchText && filteredItems.length === 0) {
        itemsToDisplay = [{ id: searchText, label: searchText }];
    }

    // Group items by section
    const groupedItems = itemsToDisplay.reduce(
        (acc, item) => {
            const section = item.section || "default";
            if (!acc[section]) {
                acc[section] = [];
            }
            acc[section].push(item);
            return acc;
        },
        { default: [], advanced: [] } as Record<string, DropDownItem[]>
    );

    // Flatten for keyboard navigation
    const flatItems = [...(groupedItems.default || []), ...(groupedItems.advanced || [])];

    // Handle click outside to close
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [isOpen]);

    // Calculate dropdown position (above vs below) and trigger onOpen callback
    useEffect(() => {
        if (isOpen) {
            // Trigger onOpen callback when dropdown opens
            onOpen?.();

            if (inputRef.current && dropdownRef.current) {
                const inputRect = inputRef.current.getBoundingClientRect();
                const spaceBelow = window.innerHeight - inputRect.bottom;

                // If not enough space below (less than 240px for max-h-60), open above
                setOpenAbove(spaceBelow < 240);
            }
        }
    }, [isOpen, onOpen]);

    // Keep focus on input while dropdown is open (e.g., after models load)
    useEffect(() => {
        if (isOpen && inputRef.current && document.activeElement !== inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen, items]);

    // Handle keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (!isOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
            e.preventDefault();
            setIsOpen(true);
            return;
        }

        switch (e.key) {
            case "ArrowDown":
                e.preventDefault();
                setHighlightedIndex(prev => (prev < flatItems.length - 1 ? prev + 1 : prev));
                break;
            case "ArrowUp":
                e.preventDefault();
                setHighlightedIndex(prev => (prev > 0 ? prev - 1 : prev));
                break;
            case "Enter":
                e.preventDefault();
                if (flatItems[highlightedIndex]) {
                    onValueChange(flatItems[highlightedIndex].id);
                    setIsOpen(false);
                    setSearchText("");
                }
                break;
            case "Escape":
                e.preventDefault();
                setIsOpen(false);
                setSearchText("");
                break;
            default:
                break;
        }
    };

    const handleInputChange = (searchValue: string) => {
        setSearchText(searchValue);
        setHighlightedIndex(0);
        setIsOpen(true);
        // If user clears the search text completely, clear the selection
        if (searchValue === "") {
            onValueChange("");
        }
    };

    const handleItemSelect = (itemId: string) => {
        onValueChange(itemId);
        setIsOpen(false);
        setSearchText("");
    };

    const handleMouseDown = () => {
        focusByMouseRef.current = true;
    };

    const handleFocus = () => {
        // Only open dropdown if focused by mouse, not keyboard
        if (focusByMouseRef.current) {
            setIsOpen(true);
        }
        focusByMouseRef.current = false;
    };

    return (
        <div ref={containerRef} className="relative w-full">
            <Input
                ref={inputRef}
                type="text"
                placeholder={placeholder}
                value={searchText || selectedItem?.label || ""}
                onChange={e => handleInputChange(e.target.value)}
                onKeyDown={handleKeyDown}
                onMouseDown={handleMouseDown}
                onFocus={handleFocus}
                disabled={disabled || isLoading}
                aria-invalid={invalid}
                className={`w-full bg-(--background-w10) pr-10 ${invalid ? "border-(--error-w100)" : ""}`}
                autoComplete="off"
            />
            {isLoading ? (
                <Loader2 className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform animate-spin" />
            ) : (
                <ChevronDown className="text-muted-foreground pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform" />
            )}

            {isOpen && (flatItems.length > 0 || searchText) && (
                <div ref={dropdownRef} className={`border-input absolute right-0 left-0 z-50 rounded-md border bg-(--background-w10) shadow-md ${openAbove ? "bottom-full mb-1" : "top-full mt-1"}`}>
                    <div className="max-h-60 overflow-y-auto bg-(--background-w10)">
                        {flatItems.length > 0 ? (
                            <>
                                {/* Default items */}
                                {groupedItems.default && groupedItems.default.length > 0 && (
                                    <div>
                                        {groupedItems.default.map((item, index) => (
                                            <button
                                                key={item.id}
                                                type="button"
                                                className={`relative flex w-full cursor-default items-start gap-2 py-1.5 pr-8 pl-2 text-left text-sm transition-colors select-none hover:bg-[var(--primary-w10)] hover:text-[var(--primary-text-w60)] ${
                                                    index === highlightedIndex ? "bg-[var(--primary-w10)] text-[var(--primary-text-w60)]" : ""
                                                }`}
                                                onClick={() => handleItemSelect(item.id)}
                                                onMouseEnter={() => setHighlightedIndex(index)}
                                            >
                                                {item.icon && <div className="mt-0.5 flex-shrink-0">{item.icon}</div>}
                                                <div className="flex-1">
                                                    <div>{renderItem ? renderItem(item) : item.label}</div>
                                                    {item.subtext && <div className="text-muted-foreground text-xs">{item.subtext}</div>}
                                                </div>
                                                {item.id === value && (
                                                    <div className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
                                                        <Check className="h-4 w-4" />
                                                    </div>
                                                )}
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {/* Divider between sections */}
                                {groupedItems.default && groupedItems.default.length > 0 && groupedItems.advanced && groupedItems.advanced.length > 0 && <div className="my-1 border-t" />}

                                {/* Advanced items */}
                                {groupedItems.advanced && groupedItems.advanced.length > 0 && (
                                    <div>
                                        {groupedItems.advanced.map((item, index) => {
                                            const advancedIndex = (groupedItems.default?.length || 0) + index;
                                            return (
                                                <button
                                                    key={item.id}
                                                    type="button"
                                                    className={`relative flex w-full cursor-default items-start gap-2 py-1.5 pr-8 pl-2 text-left text-sm transition-colors select-none hover:bg-[var(--primary-w10)] hover:text-[var(--primary-text-w60)] ${
                                                        advancedIndex === highlightedIndex ? "bg-[var(--primary-w10)] text-[var(--primary-text-w60)]" : ""
                                                    }`}
                                                    onClick={() => handleItemSelect(item.id)}
                                                    onMouseEnter={() => setHighlightedIndex(advancedIndex)}
                                                >
                                                    {item.icon && <div className="mt-0.5 flex-shrink-0">{item.icon}</div>}
                                                    <div className="flex-1">
                                                        <div>{renderItem ? renderItem(item) : item.label}</div>
                                                        {item.subtext && <div className="text-muted-foreground text-xs">{item.subtext}</div>}
                                                    </div>
                                                    {item.id === value && (
                                                        <div className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
                                                            <Check className="h-4 w-4" />
                                                        </div>
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </>
                        ) : searchText ? (
                            <div className="text-muted-foreground py-1.5 pr-8 pl-2 text-sm">No items found</div>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
};
