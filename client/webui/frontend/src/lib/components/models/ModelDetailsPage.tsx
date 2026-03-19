import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Pencil, Trash2, Ellipsis } from "lucide-react";

import { Button, Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components/ui";
import { EmptyState, Footer, PageContentWrapper, PageSection, PageLabelWithValue, PageLabel, Metadata } from "@/lib/components/common";
import { Header } from "@/lib/components/header";

import { useModelConfigs } from "@/lib/api/models";
import { PROVIDER_DISPLAY_NAMES, AUTH_TYPE_LABELS } from "./common";
import { ModelProviderIcon } from "./ModelProviderIcon";

export const ModelDetailsPage = () => {
    const navigate = useNavigate();
    const { alias: modelAlias } = useParams<{ alias: string }>();
    const { data: modelConfigs = [], isLoading: modelConfigsLoading } = useModelConfigs();

    const modelToView = useMemo(() => {
        if (!modelAlias) return null;
        return modelConfigs.find(m => m.alias.toLowerCase() === modelAlias.toLowerCase()) || null;
    }, [modelAlias, modelConfigs]);

    const handleBack = () => {
        navigate(`/agents?tab=models`);
    };

    const menuActions = useMemo(() => {
        const actions: MenuAction[] = [
            {
                id: "delete",
                label: "Delete",
                onClick: () => {},
                icon: <Trash2 />,
                iconPosition: "left",
                disabled: true,
                // TODO: Enable delete in PR #5 after implementing backend DELETE endpoint
            },
        ];
        return actions;
    }, []);

    const headerButtons = useMemo(() => {
        return [
            <Button
                key="edit"
                variant="ghost"
                onClick={() => {}}
                title="Edit Model"
                disabled={true}
                // TODO: Enable edit in PR #4
            >
                <Pencil />
                Edit
            </Button>,
            <Popover key="more-menu">
                <PopoverTrigger asChild>
                    <Button variant="ghost" title="More" data-testid="modelMoreButton">
                        <Ellipsis className="h-5 w-5" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent align="end" side="bottom" className="w-auto" sideOffset={0}>
                    <Menu actions={menuActions} />
                </PopoverContent>
            </Popover>,
        ];
    }, []);

    const title = modelToView ? modelToView.alias : "N/A";

    return (
        <div className="flex h-full w-full min-w-4xl flex-col overflow-hidden">
            <Header title={title} breadcrumbs={[{ label: "Models", onClick: () => navigate("/agents?tab=models") }, { label: title }]} buttons={headerButtons} />

            {modelConfigsLoading ? (
                <EmptyState variant="loading" title="Loading Models..." />
            ) : !modelToView ? (
                <EmptyState variant="error" title="Model Not Found" buttons={[{ text: "Go To Models", variant: "default", onClick: () => navigate("/agents?tab=models") }]} />
            ) : (
                <PageContentWrapper>
                    <PageSection className="gap-4">
                        <div className="font-semibold">Model Details</div>
                        {modelToView.description && (
                            <PageLabelWithValue className="flex gap-2">
                                <PageLabel>Description</PageLabel>
                                <div className="whitespace-pre-wrap">{modelToView.description}</div>
                            </PageLabelWithValue>
                        )}

                        <PageLabelWithValue className="flex gap-2">
                            <PageLabel>Model Provider</PageLabel>
                            <div className="flex items-center gap-2">
                                <ModelProviderIcon provider={modelToView.provider} size="xs" />
                                <span>{PROVIDER_DISPLAY_NAMES[modelToView.provider] || modelToView.provider}</span>
                            </div>
                        </PageLabelWithValue>
                    </PageSection>

                    <PageSection className="gap-4">
                        <div className="pt-6 font-semibold">Model Connection Details</div>
                        <PageLabelWithValue className="flex gap-2">
                            <PageLabel>Model Name</PageLabel>
                            <div>{modelToView.modelName}</div>
                        </PageLabelWithValue>

                        {modelToView.apiBase && (
                            <PageLabelWithValue className="flex gap-2">
                                <PageLabel>URL</PageLabel>
                                <div>{modelToView.apiBase}</div>
                            </PageLabelWithValue>
                        )}

                        <PageLabelWithValue className="flex gap-2">
                            <PageLabel>Authentication</PageLabel>
                            <div>{AUTH_TYPE_LABELS[modelToView.authType ?? "none"] ?? modelToView.authType}</div>
                        </PageLabelWithValue>

                        {Object.keys(modelToView.modelParams).length > 0 && (
                            <PageLabelWithValue className="flex gap-2">
                                <PageLabel>Model Parameters</PageLabel>
                                <div className="space-y-1">
                                    {Object.entries(modelToView.modelParams).map(([key, value]) => (
                                        <div key={key}>
                                            <span className="font-medium">{key}:</span> {String(value)}
                                        </div>
                                    ))}
                                </div>
                            </PageLabelWithValue>
                        )}
                    </PageSection>

                    <Metadata
                        metadata={{
                            id: modelToView.id,
                            createdBy: modelToView.createdBy,
                            createdTime: new Date(modelToView.createdTime).toISOString(),
                            updatedBy: modelToView.updatedBy,
                            updatedTime: new Date(modelToView.updatedTime).toISOString(),
                        }}
                    />
                </PageContentWrapper>
            )}

            <Footer>
                <Button variant="outline" title="Close" onClick={handleBack}>
                    Close
                </Button>
            </Footer>
        </div>
    );
};
