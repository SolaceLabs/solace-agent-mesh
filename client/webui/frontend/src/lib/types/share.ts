/**
 * TypeScript types for chat sharing feature
 *
 * FE-facing types use camelCase. Request types sent to the backend use snake_case
 * to match the API contract. The service layer handles mapping where needed.
 */

import type { MessageBubble, TaskMetadata } from "./storage";

export type ShareAccessType = "public" | "authenticated" | "domain-restricted";

export interface ShareLink {
    shareId: string;
    sessionId: string;
    title: string;
    isPublic: boolean;
    requireAuthentication: boolean;
    allowedDomains: string[];
    accessType: ShareAccessType;
    createdTime: number;
    shareUrl: string;
}

export interface ShareLinkItem {
    shareId: string;
    sessionId: string;
    title: string;
    isPublic: boolean;
    requireAuthentication: boolean;
    allowedDomains: string[];
    accessType: ShareAccessType;
    createdTime: number;
    messageCount: number;
}

export interface CreateShareLinkRequest {
    require_authentication?: boolean;
    allowed_domains?: string[];
}

export interface UpdateShareLinkRequest {
    require_authentication?: boolean;
    allowed_domains?: string[];
}

export interface SharedTaskEvents {
    taskId: string;
    events: SharedTaskEvent[];
    initialRequestText?: string;
}

export interface SharedTaskEvent {
    eventType: string;
    timestamp: string;
    solaceTopic: string;
    direction: string;
    sourceEntity: string;
    targetEntity: string;
    messageId: string | null;
    taskId: string;
    payloadSummary: {
        method: string;
        paramsPreview: string | null;
    };
    fullPayload: Record<string, unknown>;
}

export interface SharedSessionView {
    shareId: string;
    title: string;
    createdTime: number;
    accessType: ShareAccessType;
    tasks: SharedTask[];
    artifacts: SharedArtifact[];
    taskEvents?: Record<string, SharedTaskEvents> | null;
    isOwner?: boolean;
    sessionId?: string | null;
    snapshotTime?: number | null;
}

export interface SharedTask {
    id: string;
    sessionId: string;
    userId: string;
    userMessage?: string;
    messageBubbles: MessageBubble[];
    taskMetadata?: TaskMetadata | null;
    createdTime: number;
    /** A2A task ID for workflow lookup (may differ from chat task id) */
    workflowTaskId?: string;
}

export interface SharedArtifact {
    filename: string;
    mimeType: string;
    size: number;
    lastModified?: string | null;
    version?: number | null;
    versionCount?: number | null;
    description?: string | null;
    source?: string | null;
}

export interface ShareLinksListResponse {
    data: ShareLinkItem[];
    pageNumber: number;
    pageSize: number;
    totalPages: number;
    totalCount: number;
    nextPage: number | null;
}

// User-specific sharing types

export interface SharedLinkUserInfo {
    userEmail: string;
    accessLevel: string;
    addedAt: number;
    originalAccessLevel?: string | null;
    originalAddedAt?: number | null;
}

export interface ShareUsersResponse {
    shareId: string;
    ownerEmail: string;
    users: SharedLinkUserInfo[];
}

export interface AddShareUserRequest {
    user_email: string;
    access_level?: string;
}

export interface BatchAddShareUsersRequest {
    shares: AddShareUserRequest[];
}

export interface BatchAddShareUsersResponse {
    addedCount: number;
    users: SharedLinkUserInfo[];
}

export interface BatchDeleteShareUsersRequest {
    user_emails: string[];
}

export interface BatchDeleteShareUsersResponse {
    deletedCount: number;
}

// Shared-with-me types

export interface SharedWithMeItem {
    shareId: string;
    title: string;
    ownerEmail: string;
    accessLevel: string;
    sharedAt: number; // epoch ms
    shareUrl: string;
    sessionId?: string | null; // Original session ID
}

export interface ForkSharedChatResponse {
    sessionId: string;
    sessionName: string;
    message: string;
}
