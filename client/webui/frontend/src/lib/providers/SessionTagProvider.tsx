import React, { createContext, useContext, useCallback, useEffect } from "react";
import { useSessionTags, type SessionTag } from "@/lib/hooks/useSessionTags";

interface SessionTagContextValue {
    tags: SessionTag[];
    loading: boolean;
    error: string | null;
    refreshTags: () => Promise<void>;
    createTag: (request: { tag: string; description?: string; addToSession?: boolean; sessionId?: string }) => Promise<SessionTag | null>;
    updateTag: (oldTag: string, request: { tag?: string; description?: string; position?: number }) => Promise<SessionTag | null>;
    deleteTag: (tag: string) => Promise<boolean>;
    updateSessionTags: (sessionId: string, sessionTags: string[]) => Promise<string[] | null>;
}

const SessionTagContext = createContext<SessionTagContextValue | undefined>(undefined);

export const useSessionTagContext = () => {
    const context = useContext(SessionTagContext);
    if (!context) {
        throw new Error("useSessionTagContext must be used within a SessionTagProvider");
    }
    return context;
};

interface SessionTagProviderProps {
    children: React.ReactNode;
}

export const SessionTagProvider: React.FC<SessionTagProviderProps> = ({ children }) => {
    const sessionTagsHook = useSessionTags();

    // Auto-refresh tags when component mounts
    useEffect(() => {
        sessionTagsHook.fetchTags();
    }, [sessionTagsHook.fetchTags]);

    const refreshTags = useCallback(async () => {
        await sessionTagsHook.fetchTags();
    }, [sessionTagsHook.fetchTags]);

    const createTag = useCallback(
        async (request: { tag: string; description?: string; addToSession?: boolean; sessionId?: string }) => {
            const result = await sessionTagsHook.createTag(request);
            if (result) {
                // Auto-refresh after creation
                await refreshTags();
            }
            return result;
        },
        [sessionTagsHook.createTag, refreshTags]
    );

    const updateSessionTags = useCallback(
        async (sessionId: string, sessionTags: string[]) => {
            const result = await sessionTagsHook.updateSessionTags(sessionId, sessionTags);
            if (result) {
                // Auto-refresh after updating session tags to update counts
                await refreshTags();
            }
            return result;
        },
        [sessionTagsHook.updateSessionTags, refreshTags]
    );

    const value: SessionTagContextValue = {
        tags: sessionTagsHook.tags,
        loading: sessionTagsHook.loading,
        error: sessionTagsHook.error,
        refreshTags,
        createTag,
        updateTag: sessionTagsHook.updateTag,
        deleteTag: sessionTagsHook.deleteTag,
        updateSessionTags,
    };

    return <SessionTagContext.Provider value={value}>{children}</SessionTagContext.Provider>;
};
