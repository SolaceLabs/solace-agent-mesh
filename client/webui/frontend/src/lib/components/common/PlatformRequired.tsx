import type { ReactNode } from "react";
import { useConfigContext } from "@/lib/hooks";
import { EmptyState } from "./EmptyState";
import { ServerOff } from "lucide-react";

interface PlatformRequiredProps {
    children: ReactNode;
    title?: string;
    subtitle?: string;
}

export function PlatformRequired({
    children,
    title = "Platform Service Not Configured",
    subtitle = "This feature requires the platform service to be configured.",
}: PlatformRequiredProps) {
    const { platformConfigured } = useConfigContext();

    if (!platformConfigured) {
        return (
            <EmptyState
                title={title}
                subtitle={subtitle}
                variant="noImage"
                image={<ServerOff className="h-24 w-24 text-gray-400" strokeWidth={1} />}
            />
        );
    }

    return <>{children}</>;
}
