import { useState, useCallback, useEffect } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/lib/components/ui/input";
import { Button } from "@/lib/components/ui/button";
import { useDebounce } from "@/lib/hooks/useDebounce";
import { useConfigContext } from "@/lib/hooks";
import { authenticatedFetch } from "@/lib/utils/api";
import type { Session } from "@/lib/types";

interface SessionSearchProps {
    onSessionSelect: (sessionId: string) => void;
    projectId?: string | null;
}

interface SearchResult {
    data: Session[];
    meta: {
        total: number;
        page: number;
        pageSize: number;
        totalPages: number;
    };
}

export const SessionSearch = ({ onSessionSelect, projectId }: SessionSearchProps) => {
    const { configServerUrl } = useConfigContext();
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<Session[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);
    const debouncedSearchQuery = useDebounce(searchQuery, 300);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const performSearch = useCallback(async (query: string) => {
        if (!query.trim()) {
            setSearchResults([]);
            setShowResults(false);
            return;
        }

        setIsSearching(true);
        try {
            const params = new URLSearchParams({
                query: query.trim(),
                page_number: "1",
                page_size: "20",
            });

            if (projectId) {
                params.append("project_id", projectId);
            }

            const response = await authenticatedFetch(
                `${apiPrefix}/sessions/search?${params.toString()}`,
                { credentials: "include" }
            );

            if (!response.ok) {
                throw new Error("Search failed");
            }

            const data: SearchResult = await response.json();
            setSearchResults(data.data || []);
            setShowResults(true);
        } catch (error) {
            console.error("Search error:", error);
            setSearchResults([]);
        } finally {
            setIsSearching(false);
        }
    }, [apiPrefix, projectId]);

    useEffect(() => {
        performSearch(debouncedSearchQuery);
    }, [debouncedSearchQuery, performSearch]);

    const handleClear = () => {
        setSearchQuery("");
        setSearchResults([]);
        setShowResults(false);
    };

    const handleSessionClick = (sessionId: string) => {
        onSessionSelect(sessionId);
        handleClear();
    };

    return (
        <div className="relative w-full">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                    type="text"
                    placeholder="Search chats..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 pr-9"
                />
                {searchQuery && (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 p-0"
                        onClick={handleClear}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                )}
            </div>

            {showResults && (
                <div className="absolute z-50 mt-2 w-full rounded-md border bg-popover p-2 shadow-md">
                    {isSearching ? (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            Searching...
                        </div>
                    ) : searchResults.length > 0 ? (
                        <div className="max-h-[300px] overflow-y-auto">
                            {searchResults.map((session) => (
                                <button
                                    key={session.id}
                                    onClick={() => handleSessionClick(session.id)}
                                    className="w-full rounded-sm px-3 py-2 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                                >
                                    <div className="font-medium">
                                        {session.name || "Untitled Session"}
                                    </div>
                                    {session.projectName && (
                                        <div className="text-xs text-muted-foreground">
                                            Project: {session.projectName}
                                        </div>
                                    )}
                                    <div className="text-xs text-muted-foreground">
                                        {new Date(session.updatedTime).toLocaleDateString()}
                                    </div>
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="p-4 text-center text-sm text-muted-foreground">
                            No results found
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};