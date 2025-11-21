/**
 * API client functions for token usage tracking
 */

import type { ApiResponse, CurrentUsage, MonthlyUsageHistory, QuotaStatus, TransactionsResponse, AllUsersResponse, SetQuotaRequest, UserQuotaConfig, ResetUsageResponse } from "../types/token-usage";

const API_BASE = "/api/v1";

/**
 * Fetch wrapper with error handling
 */
async function fetchApi<T>(url: string, options?: RequestInit): Promise<ApiResponse<T>> {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...options?.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error [${url}]:`, error);
        throw error;
    }
}

// ============================================================================
// USER API FUNCTIONS
// ============================================================================

/**
 * Get current month usage for the authenticated user
 */
export async function getCurrentUsage(): Promise<CurrentUsage> {
    const response = await fetchApi<CurrentUsage>(`${API_BASE}/usage/current`);
    return response.data;
}

/**
 * Get historical usage for the authenticated user
 */
export async function getUsageHistory(months: number = 6): Promise<MonthlyUsageHistory[]> {
    const response = await fetchApi<MonthlyUsageHistory[]>(`${API_BASE}/usage/history?months=${months}`);
    return response.data;
}

/**
 * Get quota status for the authenticated user
 */
export async function getQuotaStatus(): Promise<QuotaStatus> {
    const response = await fetchApi<QuotaStatus>(`${API_BASE}/usage/quota`);
    return response.data;
}

/**
 * Get transaction history for the authenticated user
 */
export async function getTransactions(params?: { task_id?: string; limit?: number; offset?: number }): Promise<TransactionsResponse> {
    const queryParams = new URLSearchParams();
    if (params?.task_id) queryParams.append("task_id", params.task_id);
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    if (params?.offset) queryParams.append("offset", params.offset.toString());

    const url = `${API_BASE}/usage/transactions${queryParams.toString() ? `?${queryParams}` : ""}`;
    const response = await fetchApi<TransactionsResponse>(url);
    return response.data;
}

// ============================================================================
// ADMIN API FUNCTIONS
// ============================================================================

/**
 * Get usage status for all users (admin only)
 */
export async function getAllUsersUsage(params?: { limit?: number; offset?: number }): Promise<AllUsersResponse> {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    if (params?.offset) queryParams.append("offset", params.offset.toString());

    const url = `${API_BASE}/admin/usage/users${queryParams.toString() ? `?${queryParams}` : ""}`;
    const response = await fetchApi<AllUsersResponse>(url);
    return response.data;
}

/**
 * Set custom quota for a user (admin only)
 */
export async function setUserQuota(request: SetQuotaRequest): Promise<UserQuotaConfig> {
    const response = await fetchApi<UserQuotaConfig>(`${API_BASE}/admin/usage/quota/set`, {
        method: "POST",
        body: JSON.stringify(request),
    });
    return response.data;
}

/**
 * Reset monthly usage for a user (admin only)
 */
export async function resetUserUsage(userId: string): Promise<ResetUsageResponse> {
    const response = await fetchApi<ResetUsageResponse>(`${API_BASE}/admin/usage/quota/reset?user_id=${userId}`, {
        method: "POST",
    });
    return response.data;
}

/**
 * Activate a user's quota (admin only)
 */
export async function activateUser(userId: string): Promise<UserQuotaConfig> {
    const response = await fetchApi<UserQuotaConfig>(`${API_BASE}/admin/usage/users/${userId}/activate`, {
        method: "POST",
    });
    return response.data;
}

/**
 * Deactivate a user's quota (admin only)
 */
export async function deactivateUser(userId: string): Promise<UserQuotaConfig> {
    const response = await fetchApi<UserQuotaConfig>(`${API_BASE}/admin/usage/users/${userId}/deactivate`, {
        method: "POST",
    });
    return response.data;
}

/**
 * Get usage distribution by model (admin only)
 */
export async function getUsageByModel(days: number = 30): Promise<Record<string, unknown>> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/admin/usage/analytics/models?days=${days}`);
    return response.data;
}

/**
 * Get usage trends over time (admin only)
 */
export async function getUsageTrends(days: number = 30): Promise<Record<string, unknown>> {
    const response = await fetchApi<Record<string, unknown>>(`${API_BASE}/admin/usage/analytics/trends?days=${days}`);
    return response.data;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format credits as USD string
 */
export function formatCreditsAsUSD(credits: number): string {
    const usd = credits / 1_000_000;
    return `$${usd.toFixed(4)}`;
}

/**
 * Parse USD string to credits
 */
export function parseUSDToCredits(usd: string): number {
    const amount = parseFloat(usd.replace("$", ""));
    return Math.round(amount * 1_000_000);
}

/**
 * Format large numbers with commas
 */
export function formatNumber(num: number): string {
    return num.toLocaleString();
}

/**
 * Calculate percentage
 */
export function calculatePercentage(value: number, total: number): number {
    if (total === 0) return 0;
    return Math.round((value / total) * 100 * 100) / 100; // Round to 2 decimals
}

/**
 * Get usage status color based on percentage
 */
export function getUsageStatusColor(percentage: number): string {
    if (percentage >= 90) return "red";
    if (percentage >= 75) return "orange";
    if (percentage >= 50) return "yellow";
    return "green";
}

/**
 * Format timestamp to readable date
 */
export function formatTimestamp(timestamp: number): string {
    return new Date(timestamp).toLocaleString();
}

/**
 * Format month string to readable format
 */
export function formatMonth(month: string): string {
    const [year, monthNum] = month.split("-");
    const date = new Date(parseInt(year), parseInt(monthNum) - 1);
    return date.toLocaleDateString("en-US", { year: "numeric", month: "long" });
}
