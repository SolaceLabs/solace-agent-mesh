import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Button, EmptyState, Header } from "@/lib/components";
import { Input } from "@/lib/components/ui";
import { Plus, RefreshCcw, Search } from "lucide-react";
import { useApps } from "@/lib/hooks/useApps";
import type { App } from "@/lib/types";
import { AppCard } from "../apps/AppCard";
import { DeleteAppDialog } from "../apps/DeleteAppDialog";
import type { AppSettingsUpdate } from "../apps/AppSettingsDialog";

export function AppsPage() {
    const navigate = useNavigate();
    const { apps, loading, error, refetch, updateApp, deleteApp, setAppTags, generateIcon, generatingIconFor } = useApps();
    const [searchQuery, setSearchQuery] = useState("");
    const [appToDelete, setAppToDelete] = useState<App | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Filter apps based on search query (name, description, or tags)
    const filteredApps = useMemo(() => {
        if (!searchQuery.trim()) return apps;
        const query = searchQuery.toLowerCase();
        return apps.filter((app) => {
            const nameMatch = app.name.toLowerCase().includes(query);
            const descMatch = app.description?.toLowerCase().includes(query);
            const tagMatch = app.tags?.some((tag) => tag.toLowerCase().includes(query));
            return nameMatch || descMatch || tagMatch;
        });
    }, [apps, searchQuery]);

    // Split apps into My Apps and Public Apps
    // My Apps: apps owned by the current user (isOwner from backend, or fallback to true for backwards compat)
    // Public Apps: all public apps that are deployed (have at least one environment version)
    const { myApps, publicApps } = useMemo(() => {
        const my: App[] = [];
        const pub: App[] = [];

        filteredApps.forEach((app) => {
            // My Apps: apps where the user is the owner
            // Fallback: if isOwner is undefined (old backend), assume all returned apps are owned
            // (since old backend only returned user's own apps)
            const isOwner = app.isOwner ?? true;
            if (isOwner) {
                my.push(app);
            }

            // Public Apps: public apps that have at least one deployment
            if (app.isPublic) {
                const hasAnyDeployment = app.devVersion || app.stagingVersion || app.prodVersion;
                if (hasAnyDeployment) {
                    pub.push(app);
                }
            }
        });

        return { myApps: my, publicApps: pub };
    }, [filteredApps]);

    const handleCreateApp = () => {
        navigate("/apps/new");
    };

    const handleOpenApp = (app: App) => {
        // Card click only opens prod version - for dev/staging use the menu
        if (app.prodVersion) {
            navigate(`/apps/${app.appId}/view`);
        } else {
            // No prod version - open editor
            navigate(`/apps/${app.appId}/edit`);
        }
    };

    const handleViewEnvironment = (appId: string, env: "dev" | "staging" | "prod") => {
        navigate(`/apps/${appId}/view?env=${env}`);
    };

    const handleEditApp = (appId: string) => {
        navigate(`/apps/${appId}/edit`);
    };

    const handleSettingsSave = async (appId: string, updates: AppSettingsUpdate): Promise<boolean> => {
        return await updateApp(appId, updates);
    };

    const handleSaveTags = async (appId: string, tags: string[]): Promise<boolean> => {
        return await setAppTags(appId, tags);
    };

    const handleGenerateIcon = async (appId: string) => {
        return await generateIcon(appId);
    };

    const handleDeleteApp = async () => {
        if (!appToDelete) return;
        setIsDeleting(true);
        try {
            await deleteApp(appToDelete.appId);
            setAppToDelete(null);
        } finally {
            setIsDeleting(false);
        }
    };

    const renderAppGrid = (appList: App[], hideOwnerFeatures = false) => (
        <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
            {appList.map((app) => (
                <AppCard
                    key={app.appId}
                    app={app}
                    onClick={() => handleOpenApp(app)}
                    onEdit={() => handleEditApp(app.appId)}
                    onViewEnvironment={(env) => handleViewEnvironment(app.appId, env)}
                    onSettingsSave={(updates) => handleSettingsSave(app.appId, updates)}
                    onSaveTags={(tags) => handleSaveTags(app.appId, tags)}
                    onGenerateIcon={() => handleGenerateIcon(app.appId)}
                    generatingIcon={generatingIconFor === app.appId}
                    hideOwnerFeatures={hideOwnerFeatures}
                    onDelete={hideOwnerFeatures ? undefined : () => setAppToDelete(app)}
                />
            ))}
        </div>
    );

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Apps"
                subtitle="Build React applications through conversation"
                buttons={[
                    <Button
                        key="create"
                        data-testid="createApp"
                        variant="default"
                        onClick={handleCreateApp}
                    >
                        <Plus className="size-4" />
                        Create App
                    </Button>,
                    <Button
                        key="refresh"
                        data-testid="refreshApps"
                        disabled={loading}
                        variant="ghost"
                        title="Refresh Apps"
                        onClick={() => refetch()}
                    >
                        <RefreshCcw className="size-4" />
                        Refresh
                    </Button>,
                ]}
            />

            <div className="flex-1 overflow-auto p-6">
                {/* Search Bar */}
                {!loading && !error && apps.length > 0 && (
                    <div className="mb-6 max-w-md">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                placeholder="Search apps by name, description, or tags..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9"
                            />
                        </div>
                    </div>
                )}

                {loading ? (
                    <EmptyState title="Loading apps..." variant="loading" />
                ) : error ? (
                    <EmptyState
                        variant="error"
                        title="Error loading apps"
                        subtitle={error}
                    />
                ) : apps.length === 0 ? (
                    <EmptyState
                        title="No apps yet"
                        subtitle="Create your first app to get started"
                        action={{
                            label: "Create App",
                            onClick: handleCreateApp,
                        }}
                    />
                ) : filteredApps.length === 0 ? (
                    <EmptyState
                        title="No matching apps"
                        subtitle={`No apps found matching "${searchQuery}"`}
                    />
                ) : (
                    <div className="space-y-8">
                        {/* My Apps Section */}
                        {myApps.length > 0 && (
                            <section>
                                <h2 className="text-lg font-semibold mb-4">My Apps</h2>
                                {renderAppGrid(myApps)}
                            </section>
                        )}

                        {/* Public Apps Section */}
                        {publicApps.length > 0 && (
                            <section>
                                <h2 className="text-lg font-semibold mb-4">Public Apps</h2>
                                {renderAppGrid(publicApps, true)}
                            </section>
                        )}
                    </div>
                )}
            </div>

            <DeleteAppDialog
                isOpen={!!appToDelete}
                onClose={() => setAppToDelete(null)}
                onConfirm={handleDeleteApp}
                app={appToDelete}
                isDeleting={isDeleting}
            />
        </div>
    );
}
