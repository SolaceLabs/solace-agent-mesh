/**
 * Types for session context usage and compaction.
 */

export interface ContextUsage {
    sessionId: string;
    currentContextTokens: number;
    promptTokens: number;
    completionTokens: number;
    cachedTokens: number;
    maxInputTokens: number;
    usagePercentage: number;
    model: string;
    totalEvents: number;
    totalMessages: number;
    totalTasks: number;
    hasCompaction: boolean;
}

export interface CompactSessionRequest {
    model?: string;
    compactionPercentage?: number;
}

export interface CompactSessionResponse {
    eventsCompacted: number;
    summary: string;
    remainingEvents: number;
    remainingTokens: number;
}
