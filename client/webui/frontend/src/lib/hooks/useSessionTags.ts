import { useState, useCallback } from "react";
import { authenticatedFetch } from "@/lib/utils/api";
import { useConfigContext } from "@/lib/hooks";

export interface SessionTag {
    id: string;
    userId: string;
    tag: string;
    description?: string;
    count: number;
    position: number;
    createdTime: number;
    updatedTime?: number;
}

export interface CreateSessionTagRequest {
    tag: string;
    description?: string;
    addToSession?: boolean;
    sessionId?: string;
}

export interface UpdateSessionTagRequest {
    tag?: string;
    description?: string;
    position?: number;
}

export const useSessionTags = () => {
    const { configServerUrl } = useConfigContext();
    const [tags, setTags] = useState<SessionTag[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchTags = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${configServerUrl}/api/v1/session-tags`);
            if (response.ok) {
                const data = await response.json();
                setTags(data);
            } else {
                setError(`Failed to fetch tags: ${response.status} ${response.statusText}`);
            }
        } catch (err) {
            setError(`Error fetching tags: ${err}`);
        } finally {
            setLoading(false);
        }
    }, [configServerUrl]);

    const createTag = useCallback(
        async (request: CreateSessionTagRequest): Promise<SessionTag | null> => {
            setLoading(true);
            setError(null);
            try {
                const response = await authenticatedFetch(`${configServerUrl}/api/v1/session-tags`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(request),
                });

                if (response.ok) {
                    const newTag = await response.json();
                    setTags(prev => [...prev, newTag]);
                    return newTag;
                } else {
                    setError(`Failed to create tag: ${response.status} ${response.statusText}`);
                    return null;
                }
            } catch (err) {
                setError(`Error creating tag: ${err}`);
                return null;
            } finally {
                setLoading(false);
            }
        },
        [configServerUrl]
    );

    const updateTag = useCallback(
        async (oldTag: string, request: UpdateSessionTagRequest): Promise<SessionTag | null> => {
            setLoading(true);
            setError(null);
            try {
                const response = await authenticatedFetch(`${configServerUrl}/api/v1/session-tags/${encodeURIComponent(oldTag)}`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(request),
                });

                if (response.ok) {
                    const updatedTag = await response.json();
                    setTags(prev => prev.map(tag => (tag.tag === oldTag ? updatedTag : tag)));
                    return updatedTag;
                } else {
                    setError(`Failed to update tag: ${response.status} ${response.statusText}`);
                    return null;
                }
            } catch (err) {
                setError(`Error updating tag: ${err}`);
                return null;
            } finally {
                setLoading(false);
            }
        },
        [configServerUrl]
    );

    const deleteTag = useCallback(
        async (tag: string): Promise<boolean> => {
            setLoading(true);
            setError(null);
            try {
                const response = await authenticatedFetch(`${configServerUrl}/api/v1/session-tags/${encodeURIComponent(tag)}`, {
                    method: "DELETE",
                });

                if (response.ok) {
                    setTags(prev => prev.filter(t => t.tag !== tag));
                    return true;
                } else {
                    setError(`Failed to delete tag: ${response.status} ${response.statusText}`);
                    return false;
                }
            } catch (err) {
                setError(`Error deleting tag: ${err}`);
                return false;
            } finally {
                setLoading(false);
            }
        },
        [configServerUrl]
    );

    const updateSessionTags = useCallback(
        async (sessionId: string, sessionTags: string[]): Promise<string[] | null> => {
            setLoading(true);
            setError(null);
            try {
                const response = await authenticatedFetch(`${configServerUrl}/api/v1/session-tags/session/${sessionId}`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ tags: sessionTags }),
                });

                if (response.ok) {
                    const updatedTags = await response.json();
                    // Refresh tags to get updated counts
                    await fetchTags();
                    return updatedTags;
                } else {
                    setError(`Failed to update session tags: ${response.status} ${response.statusText}`);
                    return null;
                }
            } catch (err) {
                setError(`Error updating session tags: ${err}`);
                return null;
            } finally {
                setLoading(false);
            }
        },
        [configServerUrl, fetchTags]
    );

    return {
        tags,
        loading,
        error,
        fetchTags,
        createTag,
        updateTag,
        deleteTag,
        updateSessionTags,
    };
};
