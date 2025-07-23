import { useState, useEffect, useRef } from "react";

type AutocompleteInputProps = {
  id: string;
  name?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
  autoFocus?: boolean;
  suggestions: string[];
  onFocus?: () => void;
  fetchSuggestions?: () => Promise<string[]>;
  showLoadingIndicator?: boolean;
};

export default function AutocompleteInput({
  id,
  name,
  value,
  onChange,
  placeholder = "",
  required = false,
  disabled = false,
  className = "",
  suggestions,
  onFocus,
  fetchSuggestions,
  showLoadingIndicator = false,
}: AutocompleteInputProps) {
  const [showSuggestions, setShowSuggestions] = useState<boolean>(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (suggestions && suggestions.length > 0) {
      const filtered = suggestions
        .filter((suggestion) => suggestion !== undefined && suggestion !== null)
        .filter((suggestion) =>
          suggestion.toLowerCase().includes((value || "").toLowerCase())
        );
      setFilteredSuggestions(filtered);
    } else {
      setFilteredSuggestions([]);
    }
  }, [value, suggestions]);
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(event.target as Node) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);
  const handleFocus = async () => {
    if (onFocus) {
      onFocus();
    }
    if (fetchSuggestions) {
      try {
        setIsLoading(true);
        const fetchedSuggestions = await fetchSuggestions();
        if (fetchedSuggestions && fetchedSuggestions.length > 0) {
          setFilteredSuggestions(fetchedSuggestions);
        }
      } catch (error) {
        console.error("Error fetching suggestions:", error);
      } finally {
        setIsLoading(false);
      }
    }
  };
  const handleClick = () => {
    setShowSuggestions(true);
  };
  const handleSuggestionClick = (suggestion: string) => {
    const event = {
      target: {
        name: name || id,
        value: suggestion,
      },
    } as React.ChangeEvent<HTMLInputElement>;

    onChange(event);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };
  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        id={id}
        name={name || id}
        type="text"
        value={value || ""}
        onChange={onChange}
        onFocus={handleFocus}
        onClick={handleClick}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className={`
          w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm
          focus:outline-none focus:ring-blue-500 focus:border-blue-500
          disabled:bg-gray-100 disabled:text-gray-500
          ${className}
        `}
        autoComplete="off"
      />

      {isLoading && showLoadingIndicator && (
        <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-solace-green"></div>
        </div>
      )}

      {showSuggestions && filteredSuggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className="absolute z-10 w-full mt-1 border bg-white border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
        >
          <ul>
            {filteredSuggestions.map((suggestion, index) => (
              <li
                key={index}
                onClick={() => handleSuggestionClick(suggestion)}
                onKeyDown={(e) =>
                  e.key === "Enter" && handleSuggestionClick(suggestion)
                }
                className="px-3 py-2 cursor-pointer hover:bg-stone-300"
                tabIndex={0}
              >
                {suggestion}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
