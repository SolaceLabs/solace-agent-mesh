import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, EmptyState, Header } from "@/lib/components";
import { Plus, RefreshCcw } from "lucide-react";
import { useApps } from "@/lib/hooks/useApps";
import { AppCard } from "../apps/AppCard";

export function AppsPage() {
    const navigate = useNavigate();
    const { apps, loading, error, refetch } = useApps();

    const handleCreateApp = () => {
        navigate("/apps/new");
    };

    const handleOpenApp = (appId: string, status: string) => {
        if (status === "deployed") {
            // Open deployed app view page
            navigate(`/apps/${appId}/view`);
        } else {
            // Open editor for draft apps
            navigate(`/chat?appId=${appId}`);
        }
    };

    const handleEditApp = (appId: string) => {
        // Always open editor regardless of status
        navigate(`/chat?appId=${appId}`);
    };

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
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {apps.map((app) => (
                            <AppCard
                                key={app.appId}
                                app={app}
                                onClick={() => handleOpenApp(app.appId, app.status)}
                                onEdit={() => handleEditApp(app.appId)}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
