/**
 * TypeScript types for chat sharing feature
 */

import type { MessageBubble, TaskMetadata } from "./storage";

export interface ShareLink {
    share_id: string;
    session_id: string;
    title: string;
    is_public: boolean;
    require_authentication: boolean;
    allowed_domains: string[];
    access_type: "public" | "authenticated" | "domain-restricted";
    created_time: number;
    share_url: string;
}

export interface ShareLinkItem {
    share_id: string;
    session_id: string;
    title: string;
    is_public: boolean;
    require_authentication: boolean;
    allowed_domains: string[];
    access_type: "public" | "authenticated" | "domain-restricted";
    created_time: number;
    message_count: number;
}

export interface CreateShareLinkRequest {
    require_authentication?: boolean;
    allowed_domains?: string[];
}

export interface UpdateShareLinkRequest {
    require_authentication?: boolean;
    allowed_domains?: string[];
}

export interface SharedSessionView {
    share_id: string;
    title: string;
    created_time: number;
    access_type: string;
    tasks: SharedTask[];
    artifacts: SharedArtifact[];
}

export interface SharedTask {
    id: string;
    session_id: string;
    user_id: string;
    user_message?: string;
    message_bubbles: MessageBubble[];
    task_metadata?: TaskMetadata | null;
    created_time: number;
}

export interface SharedArtifact {
    uri: string;
    version?: number;
    is_public: boolean;
}

export interface ShareLinkResponse {
    success: boolean;
    data: ShareLink;
    message: string;
}

export interface ShareLinksListResponse {
    data: ShareLinkItem[];
    pageNumber: number;
    pageSize: number;
    totalPages: number;
    totalCount: number;
    nextPage: number | null;
}

export interface SharedSessionViewResponse {
    success: boolean;
    data: SharedSessionView;
    message: string;
}

export interface DeleteShareLinkResponse {
    success: boolean;
    message: string;
}
