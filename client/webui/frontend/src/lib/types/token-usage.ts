/**
 * TypeScript types for token usage tracking
 * Uses camelCase to match SAM frontend conventions
 */

export interface UsageByModel {
    [model: string]: number;
}

export interface UsageBySource {
    [source: string]: number;
}

export interface CurrentUsage {
    userId: string;
    month: string;
    totalUsage: number;
    promptUsage: number;
    completionUsage: number;
    cachedUsage: number;
    usageByModel: UsageByModel;
    usageBySource: UsageBySource;
    costUsd: string;
    updatedAt?: number;
    // Raw token counts
    totalTokens: number;
    promptTokens: number;
    completionTokens: number;
    cachedTokens: number;
}

export interface MonthlyUsageHistory {
    month: string;
    totalUsage: number;
    promptUsage: number;
    completionUsage: number;
    cachedUsage: number;
    usageByModel: UsageByModel;
    usageBySource: UsageBySource;
    costUsd: string;
}

export interface QuotaStatus {
    userId: string;
    month: string;
    quota: number;
    currentUsage: number;
    remaining: number;
    usagePercentage: number;
    accountType: string;
    isActive: boolean;
    isCustomQuota: boolean;
    enforcementEnabled: boolean;
    quotaResetDay: number;
}

export interface TokenTransaction {
    id: number;
    taskId: string | null;
    transactionType: "prompt" | "completion" | "cached";
    model: string;
    rawTokens: number;
    tokenCost: number;
    costUsd: string;
    rate: number;
    source: string | null;
    toolName: string | null;
    context: string | null;
    createdAt: number;
}

export interface TransactionsResponse {
    transactions: TokenTransaction[];
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
}

export interface UserQuotaConfig {
    userId: string;
    monthlyQuota: number | null;
    accountType: string;
    isActive: boolean;
    updatedAt: number;
}

export interface UserUsageStatus {
    userId: string;
    quota: number;
    currentUsage: number;
    remaining: number;
    usagePercentage: number;
    accountType: string;
    isActive: boolean;
    isCustomQuota: boolean;
}

export interface AllUsersResponse {
    users: UserUsageStatus[];
    total: number;
    limit: number;
    offset: number;
    hasMore: boolean;
}

export interface SetQuotaRequest {
    userId: string;
    monthlyQuota: number | null;
    accountType?: string;
}

export interface ResetUsageResponse {
    userId: string;
    month: string;
    previousUsage: number;
    newUsage: number;
    resetAt: number;
    message?: string;
}

export interface ApiResponse<T> {
    success: boolean;
    data: T;
    error?: string;
}

// Chart data types
export interface UsageChartData {
    date: string;
    usage: number;
    cost: number;
}

export interface ModelDistributionData {
    model: string;
    usage: number;
    percentage: number;
    cost: string;
}

export interface SourceDistributionData {
    source: string;
    usage: number;
    percentage: number;
}
