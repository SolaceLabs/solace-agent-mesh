import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shareKeys } from "./keys";
import * as shareService from "./service";
import type { CreateShareLinkRequest, UpdateShareLinkRequest, BatchAddShareUsersRequest, BatchDeleteShareUsersRequest } from "../../types/share";

export function useShareLink(sessionId: string) {
    return useQuery({
        queryKey: shareKeys.link(sessionId),
        queryFn: () => shareService.getShareLinkForSession(sessionId),
        enabled: !!sessionId,
    });
}

export function useShareLinks(params?: { page?: number; pageSize?: number; search?: string }) {
    return useQuery({
        queryKey: shareKeys.list(params),
        queryFn: () => shareService.listShareLinks(params),
    });
}

export function useShareUsers(shareId: string | undefined) {
    return useQuery({
        queryKey: shareId ? shareKeys.users(shareId) : ["shares", "users", "empty"],
        queryFn: () => shareService.getShareUsers(shareId!),
        enabled: !!shareId,
    });
}

export function useSharedWithMe() {
    return useQuery({
        queryKey: shareKeys.sharedWithMe(),
        queryFn: shareService.listSharedWithMe,
    });
}

export function useSharedSessionView(shareId: string) {
    return useQuery({
        queryKey: shareKeys.view(shareId),
        queryFn: () => shareService.viewSharedSession(shareId),
        enabled: !!shareId,
    });
}

export function useCreateShareLink() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ sessionId, options }: { sessionId: string; options?: CreateShareLinkRequest }) => shareService.createShareLink(sessionId, options),
        onSuccess: (_, { sessionId }) => {
            queryClient.invalidateQueries({ queryKey: shareKeys.link(sessionId) });
            queryClient.invalidateQueries({ queryKey: shareKeys.lists() });
        },
    });
}

export function useUpdateShareLink() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, options }: { shareId: string; options: UpdateShareLinkRequest }) => shareService.updateShareLink(shareId, options),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: shareKeys.all });
        },
    });
}

export function useDeleteShareLink() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (shareId: string) => shareService.deleteShareLink(shareId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: shareKeys.all });
        },
    });
}

export function useAddShareUsers() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, data }: { shareId: string; data: BatchAddShareUsersRequest }) => shareService.addShareUsers(shareId, data),
        onSuccess: (_, { shareId }) => {
            queryClient.invalidateQueries({ queryKey: shareKeys.users(shareId) });
        },
    });
}

export function useDeleteShareUsers() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, data }: { shareId: string; data: BatchDeleteShareUsersRequest }) => shareService.deleteShareUsers(shareId, data),
        onSuccess: (_, { shareId }) => {
            queryClient.invalidateQueries({ queryKey: shareKeys.users(shareId) });
        },
    });
}

export function useUpdateShareSnapshot() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ shareId, userEmail }: { shareId: string; userEmail?: string }) => shareService.updateShareSnapshot(shareId, userEmail),
        onSuccess: (_, { shareId }) => {
            queryClient.invalidateQueries({ queryKey: shareKeys.users(shareId) });
            queryClient.invalidateQueries({ queryKey: shareKeys.view(shareId) });
        },
    });
}

export function useForkSharedChat() {
    return useMutation({
        mutationFn: (shareId: string) => shareService.forkSharedChat(shareId),
    });
}
