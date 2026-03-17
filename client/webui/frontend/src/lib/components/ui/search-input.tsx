import React from "react";
import { Search } from "lucide-react";

interface SearchInputProps {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    testid?: string;
    className?: string;
}

export const SearchInput: React.FC<SearchInputProps> = ({ value, onChange, placeholder = "Filter by name...", testid, className = "" }) => {
    return (
        <div className={`relative ${className}`}>
            <Search className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-(--secondary-text-wMain)" />
            <input type="text" data-testid={testid} placeholder={placeholder} value={value} onChange={e => onChange(e.target.value)} className="w-xs rounded-md border bg-(--background-w10) py-2 pr-3 pl-9" />
        </div>
    );
};
