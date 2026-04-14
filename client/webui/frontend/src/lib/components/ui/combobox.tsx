// This component is still in experimental phase

import { useState, useRef, useEffect, useCallback } from "react";
import type { ReactNode } from "react";
import { Check, ChevronDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input, useClickOutside } from "@/lib/components/ui";

export interface ComboBoxItem {
    id: string;
    label: string;
    icon?: ReactNode;
    subtext?: string;
    section?: "default" | "advanced";
}

interface ComboBoxProps {
    value?: string | undefined;
    onValueChange: (value: string) => void;
    items: ComboBoxItem[];
    placeholder?: string;
    disabled?: boolean;
    invalid?: boolean;
    isLoading?: boolean;
    renderItem?: (item: ComboBoxItem) => ReactNode;
    onOpen?: () => void;
    allowCustomValue?: boolean;
    noItemsFoundText?: string;
    dropdownMaxHeight?: number;
}

export const ComboBox = ({
    value,
    onValueChange,
    items,
    placeholder = "Select an option...",
    disabled,
    invalid,
    isLoading,
    renderItem,
    onOpen,
    allowCustomValue = false,
    noItemsFoundText = "No items found",
    dropdownMaxHeight = 240,
}: ComboBoxProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [searchText, setSearchText] = useState("");
    const [highlightedIndex, setHighlightedIndex] = useState(-1);
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
    if (searchText && filteredItems.length === 0 && allowCustomValue) {
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
        { default: [], advanced: [] } as Record<string, ComboBoxItem[]>
    );

    // Flatten for keyboard navigation
    const flatItems = [...(groupedItems.default || []), ...(groupedItems.advanced || [])];

    // Handle click outside to close
    const handleClickOutside = useCallback(() => setIsOpen(false), []);
    useClickOutside({ ref: containerRef, onClickOutside: handleClickOutside, enabled: isOpen });

    // Stable ref for onOpen to avoid re-triggering effect on callback identity changes
    const onOpenRef = useRef(onOpen);
    onOpenRef.current = onOpen;

    // Calculate dropdown position (above vs below) and trigger onOpen callback
    useEffect(() => {
        if (isOpen) {
            onOpenRef.current?.();

            if (inputRef.current && dropdownRef.current) {
                const inputRect = inputRef.current.getBoundingClientRect();
                const spaceBelow = window.innerHeight - inputRect.bottom;

                setOpenAbove(spaceBelow < dropdownMaxHeight);
            }
        }
    }, [isOpen]);

    // Keep focus on input while dropdown is open (e.g., after models load)
    useEffect(() => {
        if (isOpen && inputRef.current && document.activeElement !== inputRef.current) {
            inputRef.current.focus();
        }
    }, [isOpen, items.length]);

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
        // For custom-value inputs, keep the form value in sync while typing.
        // For list-only inputs, only clear the value when the user erases everything.
        if (allowCustomValue || searchValue === "") {
            onValueChange(searchValue);
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

    const renderOption = (item: ComboBoxItem, index: number) => (
        <div
            key={item.id}
            role="option"
            aria-selected={item.id === value}
            className={cn("relative flex h-auto w-full cursor-pointer justify-start gap-2 py-1.5 pr-8 pl-2 text-left text-sm font-normal text-(--primary-text-wMain) select-none", index === highlightedIndex && "bg-(--primary-w10)")}
            onClick={() => handleItemSelect(item.id)}
            onKeyDown={e => e.key === "Enter" && handleItemSelect(item.id)}
            onMouseEnter={() => setHighlightedIndex(index)}
        >
            {item.icon && <div className="flex-shrink-0">{item.icon}</div>}
            <div className="flex-1">
                {renderItem ? (
                    renderItem(item)
                ) : (
                    <>
                        <div>{item.label}</div>
                        {item.subtext && <div className="text-xs text-(--secondary-text-w50)">{item.subtext}</div>}
                    </>
                )}
            </div>
            {item.id === value && (
                <div className="absolute right-2 flex h-4 w-4 items-center justify-center">
                    <Check className="h-4 w-4" />
                </div>
            )}
        </div>
    );

    return (
        <div ref={containerRef} className="relative w-full">
            <Input
                ref={inputRef}
                type="text"
                role="combobox"
                aria-expanded={isOpen}
                aria-haspopup="listbox"
                placeholder={placeholder}
                value={searchText || selectedItem?.label || ""}
                onChange={e => handleInputChange(e.target.value)}
                onKeyDown={handleKeyDown}
                onMouseDown={handleMouseDown}
                onFocus={handleFocus}
                disabled={disabled || isLoading}
                aria-invalid={invalid}
                className={cn("w-full bg-(--background-w10) pr-10", invalid && "border-(--error-w100)")}
                autoComplete="off"
            />
            {isLoading ? (
                <Loader2 className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform animate-spin text-(--secondary-text-w50)" />
            ) : (
                <ChevronDown className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 transform text-(--secondary-text-w50)" />
            )}

            {isOpen && (flatItems.length > 0 || searchText) && (
                <div
                    ref={dropdownRef}
                    role="listbox"
                    tabIndex={-1}
                    onMouseLeave={() => setHighlightedIndex(-1)}
                    className={cn("absolute right-0 left-0 z-50 rounded-md border border-(--secondary-w20) bg-(--background-w10) shadow-md", openAbove ? "bottom-full mb-1" : "top-full mt-1")}
                >
                    <div className="overflow-y-auto bg-(--background-w10)" style={{ maxHeight: `${dropdownMaxHeight}px` }}>
                        {flatItems.length > 0 ? (
                            <>
                                {/* Default items */}
                                {groupedItems.default && groupedItems.default.length > 0 && <div>{groupedItems.default.map((item, index) => renderOption(item, index))}</div>}

                                {/* Divider between sections */}
                                {groupedItems.default && groupedItems.default.length > 0 && groupedItems.advanced && groupedItems.advanced.length > 0 && <div className="my-1 border-t" />}

                                {/* Advanced items */}
                                {groupedItems.advanced && groupedItems.advanced.length > 0 && <div>{groupedItems.advanced.map((item, index) => renderOption(item, (groupedItems.default?.length || 0) + index))}</div>}
                            </>
                        ) : searchText ? (
                            <div className="py-1.5 pr-8 pl-2 text-sm text-(--secondary-text-wMain)">{noItemsFoundText}</div>
                        ) : null}
                    </div>
                </div>
            )}
        </div>
    );
};
