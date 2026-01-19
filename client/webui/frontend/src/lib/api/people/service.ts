import { api } from "@/lib/api";
import type { PeopleSearchResponse } from "@/lib/types/projects";

/**
 * Search for users by name or email
 * @param query Search string (name or email fragment)
 * @param limit Maximum number of results (default: 10)
 */
export const searchPeople = async (query: string, limit: number = 10): Promise<PeopleSearchResponse> => {
    const response = await api.webui.get<PeopleSearchResponse>(`/api/v1/people/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    return response;
};
