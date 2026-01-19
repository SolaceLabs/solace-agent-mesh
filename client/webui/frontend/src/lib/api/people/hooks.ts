import { skipToken, useQuery } from "@tanstack/react-query";
import { peopleKeys } from "./keys";
import * as peopleService from "./service";

/**
 * React Query hook for searching people by name or email
 * @param query Search string (name or email fragment)
 * @param limit Maximum number of results (default: 10)
 * @param enabled Whether the query should run (default: true)
 */
export function useSearchPeople(query: string | null, limit: number = 10, enabled: boolean = true) {
    return useQuery({
        queryKey: query ? peopleKeys.search(query, limit) : ["people", "search", "empty"],
        queryFn: query && enabled ? () => peopleService.searchPeople(query, limit) : skipToken,
        enabled: enabled && !!query && query.length >= 2,
    });
}
