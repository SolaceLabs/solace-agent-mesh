import { api } from "@/lib/api";
import type { PeopleSearchResponse } from "@/lib/types";

export const searchPeople = async (query: string, limit: number = 10): Promise<PeopleSearchResponse> => {
    const response = await api.webui.get<PeopleSearchResponse>(`/api/v1/people/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    return response;
};
