import type { App } from "@/lib/types";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Calendar, FileCode, Edit } from "lucide-react";

interface AppCardProps {
    app: App;
    onClick: () => void;
    onEdit: () => void;
}

/**
 * Converts integer version (e.g., 123) to semantic version string (e.g., "1.2.3")
 * Backend stores versions as integers by removing dots, so we convert back to semver.
 */
function formatVersion(version: number): string {
    if (version === 0) return "0.0.0";

    const versionStr = version.toString();
    if (versionStr.length === 1) {
        return `${versionStr}.0.0`;
    } else if (versionStr.length === 2) {
        return `${versionStr[0]}.${versionStr[1]}.0`;
    } else if (versionStr.length >= 3) {
        return `${versionStr[0]}.${versionStr[1]}.${versionStr.slice(2)}`;
    }
    return versionStr;
}

export function AppCard({ app, onClick, onEdit }: AppCardProps) {
    const statusColors = {
        draft: "bg-gray-500",
        deployed: "bg-green-500",
        archived: "bg-gray-400",
    };

    const statusLabels = {
        draft: "Draft",
        deployed: "Deployed",
        archived: "Archived",
    };

    const formattedDate = new Date(app.createdTime).toLocaleDateString();

    // Clean up description by removing "SAM App: " prefix if present
    const cleanDescription = app.description?.replace(/^SAM App:\s*/i, "") || "";

    // Only show description if it's meaningful (not empty and not just the app name)
    const showDescription = cleanDescription && cleanDescription !== app.name;

    const handleEditClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent card click
        onEdit();
    };

    return (
        <Card
            className="p-4 cursor-pointer hover:shadow-lg transition-shadow"
            onClick={onClick}
        >
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                    <FileCode className="size-5 text-primary" />
                    <h3 className="font-semibold text-lg">{app.name}</h3>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleEditClick}
                        className="h-8 px-2"
                        title="Edit app"
                    >
                        <Edit className="size-4" />
                    </Button>
                    <Badge
                        variant="secondary"
                        className={`${statusColors[app.status]} text-white`}
                    >
                        {statusLabels[app.status]}
                    </Badge>
                </div>
            </div>

            {showDescription && (
                <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                    {cleanDescription}
                </p>
            )}

            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                    <Calendar className="size-3" />
                    <span>{formattedDate}</span>
                </div>
                {app.status === "deployed" && app.currentVersion > 0 && (
                    <div>
                        <span>v{formatVersion(app.currentVersion)}</span>
                    </div>
                )}
            </div>
        </Card>
    );
}
