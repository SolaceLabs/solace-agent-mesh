import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Pencil, Trash2, Ellipsis } from "lucide-react";

import { Button, Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components/ui";
import { EmptyState, Footer, PageContentWrapper, PageSection, PageLabelWithValue, PageLabel, PageValue, Metadata } from "@/lib/components/common";
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
    }, [menuActions]);

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
                            <PageLabelWithValue>
                                <PageLabel>Description</PageLabel>
                                <PageValue className="whitespace-pre-wrap">{modelToView.description}</PageValue>
                            </PageLabelWithValue>
                        )}

                        <PageLabelWithValue>
                            <PageLabel>Model Provider</PageLabel>
                            <PageValue className="flex items-center gap-2">
                                <ModelProviderIcon provider={modelToView.provider} size="xs" />
                                <span>{PROVIDER_DISPLAY_NAMES[modelToView.provider] || modelToView.provider}</span>
                            </PageValue>
                        </PageLabelWithValue>
                    </PageSection>

                    <PageSection className="gap-4">
                        <div className="pt-6 font-semibold">Model Connection Details</div>
                        <PageLabelWithValue>
                            <PageLabel>Model Name</PageLabel>
                            <PageValue>{modelToView.modelName}</PageValue>
                        </PageLabelWithValue>

                        {modelToView.apiBase && (
                            <PageLabelWithValue>
                                <PageLabel>URL</PageLabel>
                                <PageValue>{modelToView.apiBase}</PageValue>
                            </PageLabelWithValue>
                        )}

                        <PageLabelWithValue>
                            <PageLabel>Authentication</PageLabel>
                            <PageValue>{AUTH_TYPE_LABELS[modelToView.authType ?? "none"] ?? modelToView.authType}</PageValue>
                        </PageLabelWithValue>

                        {Object.keys(modelToView.modelParams).length > 0 && (
                            <PageLabelWithValue>
                                <PageLabel>Model Parameters</PageLabel>
                                <PageValue className="space-y-1">
                                    {Object.entries(modelToView.modelParams).map(([key, value]) => (
                                        <div key={key}>
                                            <span className="font-medium">{key}:</span> {String(value)}
                                        </div>
                                    ))}
                                </PageValue>
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
