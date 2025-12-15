import { Info, Lock, Globe, Server, FlaskConical, Play } from "lucide-react";
import type { App } from "@/lib/types";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

interface AppInfoPopoverProps {
    app: App;
}

/**
 * Popover component showing detailed app metadata.
 * Displays creator, timestamps, visibility, and deployment versions.
 */
export function AppInfoPopover({ app }: AppInfoPopoverProps) {
    const formatDate = (timestamp: number) => {
        return new Date(timestamp).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    };

    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent card click
    };

    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClick}
                    className="h-8 px-2"
                    title="App info"
                >
                    <Info className="size-4" />
                </Button>
            </PopoverTrigger>
            <PopoverContent
                align="end"
                side="bottom"
                className="w-64 p-3"
                sideOffset={4}
                onClick={handleClick}
            >
                <div className="space-y-3">
                    {/* Header */}
                    <div className="font-medium text-sm">About</div>

                    {/* Creator and timestamps */}
                    <div className="space-y-1.5 text-xs text-muted-foreground">
                        <div className="flex justify-between">
                            <span>Created by</span>
                            <span className="font-medium text-foreground truncate max-w-[120px]" title={app.createdByUserId}>
                                {app.createdByUserId}
                            </span>
                        </div>
                        <div className="flex justify-between">
                            <span>Created</span>
                            <span className="text-foreground">{formatDate(app.createdTime)}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>Updated</span>
                            <span className="text-foreground">{formatDate(app.updatedTime)}</span>
                        </div>
                    </div>

                    {/* Visibility */}
                    <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Visibility</span>
                        <Badge variant="outline" className="text-xs gap-1">
                            {app.isPublic ? (
                                <>
                                    <Globe className="size-3" />
                                    Public
                                </>
                            ) : (
                                <>
                                    <Lock className="size-3" />
                                    Private
                                </>
                            )}
                        </Badge>
                    </div>

                    {/* Deployments */}
                    <div className="space-y-1.5">
                        <div className="text-xs text-muted-foreground">Deployments</div>
                        <div className="space-y-1 text-xs">
                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-1.5 text-muted-foreground">
                                    <Server className="size-3" />
                                    Prod
                                </span>
                                <span className={app.prodVersion ? "text-foreground font-medium" : "text-muted-foreground"}>
                                    {app.prodVersion ? `v${app.prodVersion}` : "Not deployed"}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-1.5 text-muted-foreground">
                                    <FlaskConical className="size-3" />
                                    Staging
                                </span>
                                <span className={app.stagingVersion ? "text-foreground font-medium" : "text-muted-foreground"}>
                                    {app.stagingVersion ? `v${app.stagingVersion}` : "Not deployed"}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-1.5 text-muted-foreground">
                                    <Play className="size-3" />
                                    Dev
                                </span>
                                <span className={app.devVersion ? "text-foreground font-medium" : "text-muted-foreground"}>
                                    {app.devVersion ? `v${app.devVersion}` : "Not deployed"}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    );
}
