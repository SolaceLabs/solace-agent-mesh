/**
 * API service functions for starter card suggestions
 */

import { api } from "../client";

export interface StarterSuggestionOption {
    label: string;
    prompt: string;
}

export interface StarterSuggestionCategory {
    icon: string;
    label: string;
    description: string;
    options: StarterSuggestionOption[];
}

export interface StarterSuggestionsResponse {
    categories: StarterSuggestionCategory[];
}

export async function fetchStarterSuggestions(): Promise<StarterSuggestionsResponse> {
    return api.webui.get("/api/v1/starter-suggestions");
}
