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

export interface SharedTaskEvents {
    events: SharedTaskEvent[];
    initial_request_text: string;
}

export interface SharedTaskEvent {
    event_type: string;
    timestamp: string;
    solace_topic: string;
    direction: string;
    source_entity: string;
    target_entity: string;
    message_id: string | null;
    task_id: string;
    payload_summary: {
        method: string;
        params_preview: string | null;
    };
    full_payload: Record<string, unknown>;
}

export interface SharedSessionView {
    share_id: string;
    title: string;
    created_time: number;
    access_type: string;
    tasks: SharedTask[];
    artifacts: SharedArtifact[];
    task_events?: Record<string, SharedTaskEvents> | null;
}

export interface SharedTask {
    id: string;
    session_id: string;
    user_id: string;
    user_message?: string;
    message_bubbles: MessageBubble[];
    task_metadata?: TaskMetadata | null;
    created_time: number;
    /** A2A task ID for workflow lookup (may differ from chat task id) */
    workflow_task_id?: string;
}

export interface SharedArtifact {
    filename: string;
    mime_type: string;
    size: number;
    last_modified?: string | null;
    version?: number | null;
    version_count?: number | null;
    description?: string | null;
    source?: string | null;
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
