/**
 * User Menu Component
 * Dropdown menu with user avatar, settings, and token usage
 */

import React, { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/lib/components/ui/dropdown-menu";
import { SettingsDialog } from "@/lib/components/settings";
import { getQuotaStatus } from "../../api/token-usage-api";
import type { QuotaStatus } from "../../types/token-usage";

interface UserMenuProps {
    userName?: string;
    userEmail?: string;
    onUsageClick?: () => void;
}

export const UserMenu: React.FC<UserMenuProps> = ({ userName = "User", userEmail = "user@example.com", onUsageClick }) => {
    const [quotaStatus, setQuotaStatus] = useState<QuotaStatus | null>(null);
    const [isOpen, setIsOpen] = useState(false);

    // Get user initials
    const getInitials = (name: string): string => {
        return name
            .split(" ")
            .map(part => part[0])
            .join("")
            .toUpperCase()
            .slice(0, 2);
    };

    // Load quota status when menu opens
    useEffect(() => {
        if (isOpen) {
            loadQuotaStatus();
        }
    }, [isOpen]);

    const loadQuotaStatus = async () => {
        try {
            const status = await getQuotaStatus();
            console.log("Loaded quota status:", status);
            setQuotaStatus(status);
        } catch (error) {
            console.error("Failed to load quota status:", error);
            // Set null to hide usage section on error
            setQuotaStatus(null);
        }
    };

    const getUsageColor = (percentage: number): string => {
        if (percentage >= 90) return "text-red-600 dark:text-red-400";
        if (percentage >= 75) return "text-orange-600 dark:text-orange-400";
        if (percentage >= 50) return "text-yellow-600 dark:text-yellow-400";
        return "text-green-600 dark:text-green-400";
    };

    const getUsageBarColor = (percentage: number): string => {
        if (percentage >= 90) return "bg-red-500";
        if (percentage >= 75) return "bg-orange-500";
        if (percentage >= 50) return "bg-yellow-500";
        return "bg-green-500";
    };

    const formatNumber = (num: number): string => {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
        return num.toString();
    };

    return (
        <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
            <DropdownMenuTrigger asChild>
                <button
                    className="relative mx-auto flex w-full cursor-pointer flex-col items-center bg-[var(--color-primary-w100)] px-3 py-5 text-xs text-[var(--color-primary-text-w10)] transition-colors hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)]"
                    aria-label="User menu"
                >
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 font-semibold text-white">{getInitials(userName)}</div>
                </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent className="w-80" align="end" side="top" sideOffset={16}>
                {/* User Info */}
                <DropdownMenuLabel className="font-normal">
                    <div className="flex items-center space-x-3 py-2">
                        <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-lg font-semibold text-white">{getInitials(userName)}</div>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold text-gray-900 dark:text-white">{userName}</p>
                            <p className="truncate text-xs text-gray-500 dark:text-gray-400">{userEmail}</p>
                        </div>
                    </div>
                </DropdownMenuLabel>

                <DropdownMenuSeparator />

                {/* Token Usage Section */}
                {quotaStatus && quotaStatus.usagePercentage !== undefined && (
                    <>
                        <div className="bg-gray-50 px-2 py-3 dark:bg-gray-900/50">
                            <div className="mb-2 flex items-center justify-between">
                                <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Token Usage</span>
                                <span className={`text-xs font-semibold ${getUsageColor(quotaStatus.usagePercentage || 0)}`}>{(quotaStatus.usagePercentage || 0).toFixed(1)}%</span>
                            </div>

                            {/* Progress Bar */}
                            <div className="mb-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
                                <div className={`h-2 rounded-full ${getUsageBarColor(quotaStatus.usagePercentage || 0)} transition-all duration-300`} style={{ width: `${Math.min(quotaStatus.usagePercentage || 0, 100)}%` }}></div>
                            </div>

                            <div className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400">
                                <span>{formatNumber(quotaStatus.currentUsage || 0)} used</span>
                                <span>{formatNumber(quotaStatus.remaining || 0)} left</span>
                            </div>

                            {/* Account Type */}
                            <div className="mt-2">
                                <span className="inline-flex items-center rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-800 capitalize dark:bg-blue-900 dark:text-blue-200">{quotaStatus.accountType || "free"}</span>
                            </div>
                        </div>

                        <DropdownMenuSeparator />
                    </>
                )}

                {/* Menu Items */}
                <DropdownMenuItem
                    className="cursor-pointer hover:bg-[var(--color-primary-w90)] hover:text-[var(--color-primary-text-w10)] focus:bg-[var(--color-primary-w90)] focus:text-[var(--color-primary-text-w10)]"
                    onClick={() => {
                        setIsOpen(false);
                        onUsageClick?.();
                    }}
                >
                    <BarChart3 className="mr-2 h-4 w-4" />
                    <span>Usage Details</span>
                </DropdownMenuItem>

                {/* Settings - uses SettingsDialog component */}
                <SettingsDialog iconOnly={false} />
            </DropdownMenuContent>
        </DropdownMenu>
    );
};

export default UserMenu;
