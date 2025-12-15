import { useEffect } from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { Button } from "../ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "../ui/dialog";
import { Badge } from "../ui/badge";
import { useApp } from "@/lib/hooks";
import type { Environment } from "@/lib/types";

interface DeploymentDialogProps {
    isOpen: boolean;
    onClose: () => void;
    appId: string;
}

const ENVIRONMENT_COLORS: Record<Environment, string> = {
    dev: "bg-green-500",
    staging: "bg-yellow-500",
    prod: "bg-blue-500",
};

const ENVIRONMENT_LABELS: Record<Environment, string> = {
    dev: "Dev",
    staging: "Staging",
    prod: "Prod",
};

export function DeploymentDialog({ isOpen, onClose, appId }: DeploymentDialogProps) {
    const {
        versions,
        loadingVersions,
        fetchVersions,
        deployToEnvironment,
        deploying,
        promoteVersion,
        promoting,
    } = useApp(appId);

    // Fetch versions when dialog opens
    useEffect(() => {
        if (isOpen) {
            fetchVersions();
        }
    }, [isOpen, fetchVersions]);

    const handleTestPreview = () => {
        window.open(`/api/v1/apps/preview/${appId}/`, "_blank");
    };

    const handleTestVersion = (version: string) => {
        window.open(`/api/v1/apps/deployed/${appId}/?version=${version}`, "_blank");
    };

    const handleDeployToEnvironment = async (environment: Environment) => {
        await deployToEnvironment(environment);
    };

    const handlePromoteToEnvironment = async (version: string, environment: Environment) => {
        await promoteVersion(version, environment);
    };

    // Get environments where each version is deployed
    const getVersionEnvironments = (version: string): Environment[] => {
        if (!versions) return [];
        const envs: Environment[] = [];
        if (versions.environments.dev === version) envs.push("dev");
        if (versions.environments.staging === version) envs.push("staging");
        if (versions.environments.prod === version) envs.push("prod");
        return envs;
    };

    // Get available deploy/promote targets for a version
    const getAvailableEnvironments = (version: string, isPreview: boolean): Environment[] => {
        if (!versions) return ["dev", "staging", "prod"];

        // For preview, show all environments it's not currently deployed to
        const currentEnvs = getVersionEnvironments(version);
        return (["dev", "staging", "prod"] as Environment[]).filter(
            (env) => !currentEnvs.includes(env)
        );
    };

    const isLoading = loadingVersions || deploying || promoting;

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Deployment Management</DialogTitle>
                    <DialogDescription>
                        Deploy preview or promote existing versions to different environments.
                    </DialogDescription>
                </DialogHeader>

                {loadingVersions ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="size-6 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="space-y-6 py-4">
                        {/* Preview Section - always shown */}
                        <div className="rounded-lg border p-4 bg-muted/30">
                            {versions?.preview.available ? (
                                <>
                                    <div className="flex items-center justify-between mb-3">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-semibold">Preview</span>
                                                {versions.preview.version && (
                                                    <Badge variant="outline">
                                                        v{versions.preview.version}
                                                    </Badge>
                                                )}
                                            </div>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                Current workspace build
                                            </p>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={handleTestPreview}
                                        >
                                            <ExternalLink className="size-4 mr-1.5" />
                                            Test
                                        </Button>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {(["dev", "staging", "prod"] as Environment[]).map((env) => (
                                            <Button
                                                key={env}
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => handleDeployToEnvironment(env)}
                                                disabled={isLoading}
                                            >
                                                {deploying ? (
                                                    <Loader2 className="size-3 mr-1.5 animate-spin" />
                                                ) : null}
                                                Deploy to {ENVIRONMENT_LABELS[env]}
                                            </Button>
                                        ))}
                                    </div>
                                </>
                            ) : versions?.preview.version ? (
                                // VERSION file exists but no dist/ - show version but indicate needs build
                                <div className="text-center py-2">
                                    <div className="flex items-center justify-center gap-2 mb-2">
                                        <span className="font-semibold">Preview</span>
                                        <Badge variant="outline">v{versions.preview.version}</Badge>
                                    </div>
                                    <p className="text-muted-foreground text-sm">
                                        No build available. Ask the agent to build the app first.
                                    </p>
                                </div>
                            ) : (
                                // No VERSION file at all
                                <div className="text-center py-4">
                                    <p className="text-muted-foreground">
                                        No preview available. Ask the agent to build the app first.
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Deployed Versions Section */}
                        {versions && versions.versions.length > 0 && (
                            <>
                                <div className="flex items-center gap-2">
                                    <div className="h-px flex-1 bg-border" />
                                    <span className="text-sm text-muted-foreground">
                                        Deployed Versions
                                    </span>
                                    <div className="h-px flex-1 bg-border" />
                                </div>

                                <div className="space-y-3">
                                    {versions.versions.map((version) => {
                                        const envs = getVersionEnvironments(version);
                                        const availableEnvs = getAvailableEnvironments(version, false);

                                        return (
                                            <div
                                                key={version}
                                                className="rounded-lg border p-4"
                                            >
                                                <div className="flex items-center justify-between mb-3">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-medium">
                                                            v{version}
                                                        </span>
                                                        {envs.map((env) => (
                                                            <Badge
                                                                key={env}
                                                                className={`${ENVIRONMENT_COLORS[env]} text-white`}
                                                            >
                                                                {ENVIRONMENT_LABELS[env]}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => handleTestVersion(version)}
                                                    >
                                                        <ExternalLink className="size-4 mr-1.5" />
                                                        Test
                                                    </Button>
                                                </div>
                                                {availableEnvs.length > 0 && (
                                                    <div className="flex flex-wrap gap-2">
                                                        {availableEnvs.map((env) => (
                                                            <Button
                                                                key={env}
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() =>
                                                                    handlePromoteToEnvironment(
                                                                        version,
                                                                        env
                                                                    )
                                                                }
                                                                disabled={isLoading}
                                                            >
                                                                {promoting ? (
                                                                    <Loader2 className="size-3 mr-1.5 animate-spin" />
                                                                ) : null}
                                                                Promote to {ENVIRONMENT_LABELS[env]}
                                                            </Button>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>
                )}

                <DialogFooter>
                    <Button variant="ghost" onClick={onClose}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
