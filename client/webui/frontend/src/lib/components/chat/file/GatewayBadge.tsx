import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";
import { MessageSquare, Hash, Users } from "lucide-react";

export type GatewayType = "web" | "slack" | "teams" | string;

interface GatewayBadgeProps {
    gatewayType: GatewayType;
    externalContextId?: string | null;
    className?: string;
}

const gatewayConfig: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    slack: {
        label: "Slack",
        icon: <Hash className="h-3 w-3" />,
        color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    },
    teams: {
        label: "Teams",
        icon: <Users className="h-3 w-3" />,
        color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    },
    web: {
        label: "Web",
        icon: <MessageSquare className="h-3 w-3" />,
        color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    },
};

export const GatewayBadge = ({ gatewayType, externalContextId, className = "" }: GatewayBadgeProps) => {
    // Don't show badge for web gateway (default)
    if (!gatewayType || gatewayType === "web") {
        return null;
    }

    const config = gatewayConfig[gatewayType] || {
        label: gatewayType.charAt(0).toUpperCase() + gatewayType.slice(1),
        icon: <MessageSquare className="h-3 w-3" />,
        color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    };

    const tooltipText = externalContextId ? `${config.label}: ${externalContextId}` : config.label;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="outline" className={`flex items-center gap-1 px-1.5 py-0.5 text-xs ${config.color} ${className}`}>
                    {config.icon}
                    <span className="font-medium">{config.label}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{tooltipText}</TooltipContent>
        </Tooltip>
    );
};
