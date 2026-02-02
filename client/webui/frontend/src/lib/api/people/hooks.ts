import { useQuery } from "@tanstack/react-query";
import { peopleKeys } from "./keys";
import * as peopleService from "./service";

export function usePeopleSearch(query: string, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: peopleKeys.search(query),
        queryFn: () => peopleService.searchPeople(query),
        enabled: options?.enabled ?? query.length > 0,
        staleTime: 30000,
    });
}
