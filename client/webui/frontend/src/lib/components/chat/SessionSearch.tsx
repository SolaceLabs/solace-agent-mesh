import { useState, useCallback, useEffect } from "react";
import { Search, X } from "lucide-react";

import { api } from "@/lib/api";
import { ProjectBadge } from "@/lib/components/chat";
import { Button, Input } from "@/lib/components/ui";
import { useDebounce } from "@/lib/hooks";
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
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<Session[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showResults, setShowResults] = useState(false);
    const debouncedSearchQuery = useDebounce(searchQuery, 300);

    const performSearch = useCallback(async (query: string, currentProjectId: string | null | undefined) => {
        if (!query.trim()) {
            setSearchResults([]);
            setShowResults(false);
            return;
        }

        setIsSearching(true);
        try {
            const params = new URLSearchParams({
                query: query.trim(),
                pageNumber: "1",
                pageSize: "20",
            });

            if (currentProjectId) {
                params.append("projectId", currentProjectId);
            }

            const data: SearchResult = await api.webui.get(`/api/v1/sessions/search?${params.toString()}`);
            setSearchResults(data.data || []);
            setShowResults(true);
        } catch (error) {
            console.error("Search error:", error);
            setSearchResults([]);
        } finally {
            setIsSearching(false);
        }
    }, []);

    useEffect(() => {
        performSearch(debouncedSearchQuery, projectId);
    }, [debouncedSearchQuery, projectId, performSearch]);

    const handleClear = () => {
        setSearchQuery("");
        setSearchResults([]);
        setShowResults(false);
    };

    const handleSessionClick = (sessionId: string) => {
        onSessionSelect(sessionId);
        handleClear();
    };

    const placeholder = "Search chats by title";

    return (
        <div className="relative w-full">
            <div className="relative">
                <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
                <Input type="text" placeholder={placeholder} value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="pr-9 pl-9" />
                {searchQuery && (
                    <Button variant="ghost" size="sm" className="absolute top-1/2 right-1 h-7 w-7 -translate-y-1/2 p-0" onClick={handleClear}>
                        <X className="h-4 w-4" />
                    </Button>
                )}
            </div>

            {showResults && (
                <div className="bg-popover absolute z-50 mt-2 w-full rounded-md border p-2 shadow-md">
                    {isSearching ? (
                        <div className="text-muted-foreground p-4 text-center text-sm">Searching...</div>
                    ) : searchResults.length > 0 ? (
                        <div className="max-h-[300px] overflow-y-auto">
                            {searchResults.map(session => (
                                <button key={session.id} onClick={() => handleSessionClick(session.id)} className="hover:bg-accent hover:text-accent-foreground w-full rounded-sm px-3 py-2 text-left text-sm">
                                    <div className="mb-1 flex items-center justify-between gap-2">
                                        <div className="flex-1 truncate font-medium">{session.name || "Untitled Session"}</div>
                                        {session.projectName && <ProjectBadge text={session.projectName} />}
                                    </div>
                                    <div className="text-muted-foreground text-xs">{new Date(session.updatedTime).toLocaleDateString()}</div>
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="text-muted-foreground p-4 text-center text-sm">No results found</div>
                    )}
                </div>
            )}
        </div>
    );
};
