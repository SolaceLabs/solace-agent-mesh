/**
 * React Query hooks for share user management
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getShareUsers, addShareUsers, deleteShareUsers } from "@/lib/api/shareApi";
import type { BatchAddShareUsersRequest, BatchDeleteShareUsersRequest } from "@/lib/types/share";

// Query keys for share users
export const shareUserKeys = {
    all: ["shareUsers"] as const,
    users: (shareId: string) => [...shareUserKeys.all, shareId] as const,
};

/**
 * Hook to fetch users with access to a share link
 */
export function useShareUsers(shareId: string | null) {
    return useQuery({
        queryKey: shareUserKeys.users(shareId || ""),
        queryFn: () => getShareUsers(shareId!),
        enabled: !!shareId,
    });
}

/**
 * Hook to add users to a share link
 */
export function useAddShareUsers() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, data }: { shareId: string; data: BatchAddShareUsersRequest }) => addShareUsers(shareId, data),
        onSuccess: (_, { shareId }) => {
            queryClient.invalidateQueries({ queryKey: shareUserKeys.users(shareId) });
        },
    });
}

/**
 * Hook to remove users from a share link
 */
export function useDeleteShareUsers() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, data }: { shareId: string; data: BatchDeleteShareUsersRequest }) => deleteShareUsers(shareId, data),
        onSuccess: (_, { shareId }) => {
            queryClient.invalidateQueries({ queryKey: shareUserKeys.users(shareId) });
        },
    });
}
