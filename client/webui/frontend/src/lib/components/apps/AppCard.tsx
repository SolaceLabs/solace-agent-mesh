import { useState } from "react";
import { FileCode, MoreHorizontal, Edit, Rocket, Play, FlaskConical, Server, Settings } from "lucide-react";

import { GridCard } from "@/lib/components/common";
import { CardContent, CardDescription, CardHeader, CardTitle, Badge, Button, Popover, PopoverContent, PopoverTrigger, Menu } from "@/lib/components/ui";
import type { MenuAction } from "@/lib/components/ui/menu";
import type { App } from "@/lib/types";
import { DeploymentDialog } from "./DeploymentDialog";
import { AppInfoPopover } from "./AppInfoPopover";
import { AppSettingsDialog, type AppSettingsUpdate } from "./AppSettingsDialog";

type Environment = "dev" | "staging" | "prod";

interface AppCardProps {
    app: App;
    onClick: () => void;
    onEdit: () => void;
    onViewEnvironment: (env: Environment) => void;
    onSettingsSave: (updates: AppSettingsUpdate) => Promise<boolean>;
    onSaveTags: (tags: string[]) => Promise<boolean>;
    /** Hide status badge and owner-only actions (for public apps section) */
    hideOwnerFeatures?: boolean;
}

export function AppCard({ app, onClick, onEdit, onViewEnvironment, onSettingsSave, onSaveTags, hideOwnerFeatures = false }: AppCardProps) {
    const [menuOpen, setMenuOpen] = useState(false);
    const [isDeployDialogOpen, setIsDeployDialogOpen] = useState(false);
    const [isSettingsDialogOpen, setIsSettingsDialogOpen] = useState(false);

    // Clean up description by removing "SAM App: " prefix if present
    const cleanDescription = app.description?.replace(/^SAM App:\s*/i, "") || "";

    // Only show description if it's meaningful (not empty and not just the app name)
    const showDescription = cleanDescription && cleanDescription !== app.name;

    // Check which environments have deployments
    const hasDevVersion = !!app.devVersion;
    const hasStagingVersion = !!app.stagingVersion;
    const hasProdVersion = !!app.prodVersion;
    const hasAnyDeployment = hasDevVersion || hasStagingVersion || hasProdVersion;

    const statusColors = {
        draft: "bg-gray-500 dark:bg-gray-500/70",
        deployed: "bg-green-500 dark:bg-green-600/70",
        archived: "bg-gray-400 dark:bg-gray-400/70",
    };

    const statusLabels = {
        draft: "Draft",
        deployed: "Deployed",
        archived: "Archived",
    };

    // Build menu actions
    const menuActions: MenuAction[] = [
        {
            id: "edit",
            label: "Edit App",
            icon: <Edit size={14} />,
            onClick: () => {
                setMenuOpen(false);
                onEdit();
            },
        },
        {
            id: "settings",
            label: "App Settings",
            icon: <Settings size={14} />,
            onClick: () => {
                setMenuOpen(false);
                setIsSettingsDialogOpen(true);
            },
        },
        {
            id: "deployments",
            label: "Manage Deployments",
            icon: <Rocket size={14} />,
            onClick: () => {
                setMenuOpen(false);
                setIsDeployDialogOpen(true);
            },
        },
        // Add environment run options if deployed
        ...(hasProdVersion
            ? [
                  {
                      id: "run-prod",
                      label: `Run Prod (v${app.prodVersion})`,
                      icon: <Server size={14} />,
                      divider: true,
                      onClick: () => {
                          setMenuOpen(false);
                          onViewEnvironment("prod");
                      },
                  },
              ]
            : []),
        ...(hasStagingVersion
            ? [
                  {
                      id: "run-staging",
                      label: `Run Staging (v${app.stagingVersion})`,
                      icon: <FlaskConical size={14} />,
                      divider: !hasProdVersion,
                      onClick: () => {
                          setMenuOpen(false);
                          onViewEnvironment("staging");
                      },
                  },
              ]
            : []),
        ...(hasDevVersion
            ? [
                  {
                      id: "run-dev",
                      label: `Run Dev (v${app.devVersion})`,
                      icon: <Play size={14} />,
                      divider: !hasProdVersion && !hasStagingVersion,
                      onClick: () => {
                          setMenuOpen(false);
                          onViewEnvironment("dev");
                      },
                  },
              ]
            : []),
    ];

    return (
        <>
            <GridCard onClick={onClick}>
                <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                        <CardTitle className="flex min-w-0 flex-1 items-center gap-2" title={app.name}>
                            <FileCode className="h-6 w-6 flex-shrink-0 text-[var(--color-brand-wMain)]" />
                            <div className="text-foreground max-w-[250px] min-w-0 truncate text-lg font-semibold">{app.name}</div>
                        </CardTitle>
                        <div className="flex shrink-0 items-center gap-1">
                            <AppInfoPopover app={app} />
                            <Popover open={menuOpen} onOpenChange={setMenuOpen}>
                                <PopoverTrigger asChild>
                                    <Button variant="ghost" size="icon" className="h-8 w-8" tooltip="More options" onClick={e => e.stopPropagation()}>
                                        <MoreHorizontal className="h-4 w-4" />
                                    </Button>
                                </PopoverTrigger>
                                <PopoverContent align="end" side="bottom" className="w-52 p-1" sideOffset={0} onClick={e => e.stopPropagation()}>
                                    <Menu actions={menuActions} />
                                </PopoverContent>
                            </Popover>
                        </div>
                    </div>
                    <div className="text-muted-foreground text-xs truncate" title={app.createdByUserId}>
                        By {app.createdByUserId}
                    </div>
                </CardHeader>

                <CardContent className="flex flex-1 flex-col justify-between">
                    <div className="space-y-2">
                        {showDescription ? (
                            <CardDescription className="line-clamp-2" title={cleanDescription}>
                                {cleanDescription}
                            </CardDescription>
                        ) : (
                            <div />
                        )}
                        {app.tags && app.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                                {app.tags.slice(0, 4).map((tag) => (
                                    <Badge key={tag} variant="outline" className="text-xs px-1.5 py-0">
                                        {tag}
                                    </Badge>
                                ))}
                                {app.tags.length > 4 && (
                                    <Badge variant="outline" className="text-xs px-1.5 py-0 text-muted-foreground">
                                        +{app.tags.length - 4}
                                    </Badge>
                                )}
                            </div>
                        )}
                    </div>

                    {!hideOwnerFeatures && (
                        <div className="mt-3 flex items-center justify-end gap-2">
                            <Badge
                                variant={app.isPublic ? "secondary" : "outline"}
                                className={`flex h-6 items-center gap-1 ${app.isPublic ? "bg-blue-500 dark:bg-blue-600/70 text-white dark:text-white/80" : "text-muted-foreground"}`}
                                title={app.isPublic ? "Visible to everyone" : "Only visible to you"}
                            >
                                {app.isPublic ? "Public" : "Private"}
                            </Badge>
                            <Badge
                                variant="secondary"
                                className={`${statusColors[app.status]} text-white dark:text-white/80 flex h-6 items-center gap-1`}
                                title={statusLabels[app.status]}
                            >
                                {statusLabels[app.status]}
                            </Badge>
                        </div>
                    )}
                </CardContent>
            </GridCard>

            <DeploymentDialog
                isOpen={isDeployDialogOpen}
                onClose={() => setIsDeployDialogOpen(false)}
                appId={app.appId}
            />

            <AppSettingsDialog
                isOpen={isSettingsDialogOpen}
                onClose={() => setIsSettingsDialogOpen(false)}
                app={app}
                onSave={onSettingsSave}
                onSaveTags={onSaveTags}
            />
        </>
    );
}
