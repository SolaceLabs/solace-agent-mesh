import React, { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import { Ellipsis } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Button, Badge, Menu, Popover, PopoverContent, PopoverTrigger, type MenuAction } from "@/lib/components/ui";
import { PaginationControls, EmptyState, OnboardingBanner } from "@/lib/components/common";
import { Toast } from "@/lib/components/toast";

import { useModelConfigs } from "@/lib/api/models";
import type { ModelConfig } from "@/lib/api/models/types";
import { ModelsOnboardingView } from "./ModelsOnboardingView";
import { ModelProviderIcon } from "./ModelProviderIcon";
import { PROVIDER_DISPLAY_NAMES, getDisplayModelName, getDisplayAliasName } from "./common";

const MODELS_STORAGE_KEY = "sam-models-onboarding-dismissed";
const MODELS_HEADER = "Your Models Are Now Accessible to Your Team";
const MODELS_DESCRIPTION =
    "Existing models from your local backend configuration have been imported here and are now accessible for anyone in your organization. Going forward, changes you make in this UI will take precedence over your shared config file.";
const MODELS_LEARN_MORE_TEXT = "Learn about managing models";
const MODELS_URL = "#"; // TODO: Add documentation URL

const EMPTY_STATE_TITLE = "Match AI Models to Your Team's Workflows";
const EMPTY_STATE_DESCRIPTION =
    "Different models specialize in different use cases. Organize your models by use case and assign to agents based on what the agent needs. Start with our suggested names or create your own. The 'General' model is required but you can customize everything else to fit your workflow.";

export const ModelsView: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { data: modelConfigs = [], isLoading: modelConfigsLoading, error: modelConfigsErrorObj } = useModelConfigs();
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [highlightedModelAlias, setHighlightedModelAlias] = useState<string | null>(null);
    const [showSuccessToast, setShowSuccessToast] = useState<boolean>(false);
    const highlightedRowRef = useRef<HTMLTableRowElement>(null);

    // Check if we're coming back from creating a new model
    useEffect(() => {
        const state = location.state as { highlightModelAlias?: string } | null;
        if (state?.highlightModelAlias) {
            setHighlightedModelAlias(state.highlightModelAlias);
            setShowSuccessToast(true);

            // Clear the location state to prevent re-triggering on refresh
            navigate(location.pathname + location.search, { replace: true });

            // Auto-hide toast after 6 seconds
            const toastTimer = setTimeout(() => {
                setShowSuccessToast(false);
            }, 6000);

            // Auto-fade highlight after 4 seconds
            const highlightTimer = setTimeout(() => {
                setHighlightedModelAlias(null);
            }, 4000);

            return () => {
                clearTimeout(toastTimer);
                clearTimeout(highlightTimer);
            };
        }
    }, [location, navigate]);

    // Scroll highlighted row into view
    useEffect(() => {
        if (highlightedRowRef.current) {
            highlightedRowRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [highlightedModelAlias]);

    const modelConfigsError = modelConfigsErrorObj ? (modelConfigsErrorObj instanceof Error ? modelConfigsErrorObj.message : "Failed to load models") : null;

    const hasModels = modelConfigs && modelConfigs.length > 0;

    // Client-side pagination
    const itemsPerPage = 20;
    const totalPages = Math.ceil((modelConfigs?.length || 0) / itemsPerPage);
    const effectiveCurrentPage = Math.min(currentPage, Math.max(totalPages, 1));
    const startIndex = (effectiveCurrentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentModels = modelConfigs?.slice(startIndex, endIndex) || [];

    const handleSelectModel = (model: ModelConfig) => {
        navigate(`/models/${model.alias}`);
    };

    const handleCreateModel = () => {
        navigate("/models/new/edit");
    };

    const handleEditModel = (model: ModelConfig) => {
        navigate(`/models/${model.alias}/edit`);
    };

    const getRowMenuActions = (model: ModelConfig): MenuAction[] => [
        {
            id: "open-details",
            label: "Open Details",
            onClick: () => handleSelectModel(model),
        },
        {
            id: "edit",
            label: "Edit",
            onClick: () => handleEditModel(model),
        },
        {
            id: "delete",
            label: "Delete",
            onClick: () => {},
            disabled: true,
            divider: true,
        },
    ];

    // Loading state
    if (modelConfigsLoading) {
        return <EmptyState variant="loading" title="Loading Models..." />;
    }

    // Error state
    if (modelConfigsError) {
        return <EmptyState variant="error" title={`Error loading models: ${modelConfigsError}`} />;
    }

    return (
        <div className="flex h-full w-full flex-col overflow-hidden">
            {/* Toast Notification */}
            {showSuccessToast && (
                <div className="pointer-events-none fixed bottom-4 left-1/2 z-50 -translate-x-1/2 transform">
                    <Toast id="model-added" message="Model Added" type="success" />
                </div>
            )}

            <div className="flex h-full flex-col overflow-hidden">
                {/* Onboarding Banner - only show when models exist */}
                {hasModels && <OnboardingBanner storageKey={MODELS_STORAGE_KEY} header={MODELS_HEADER} description={MODELS_DESCRIPTION} learnMoreText={MODELS_LEARN_MORE_TEXT} learnMoreUrl={MODELS_URL} className="mx-6 mt-6" />}

                {/* Table and Pagination */}
                <div className="flex-1 overflow-y-auto px-6 py-6">
                    {currentModels.length > 0 ? (
                        <div className="rounded-xs border-[1px] border-(--secondary-w20)">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="font-semibold">
                                            <div className="pl-4">Name</div>
                                        </TableHead>
                                        <TableHead className="font-semibold">Model</TableHead>
                                        <TableHead className="font-semibold">Model Provider</TableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {currentModels.map(model => (
                                        <TableRow
                                            key={model.id}
                                            ref={highlightedModelAlias === model.alias ? highlightedRowRef : null}
                                            className={`transition-colors duration-500 ${highlightedModelAlias === model.alias ? "bg-(--success-w10)" : "hover:bg-(--primary-w10)"}`}
                                        >
                                            <TableCell className="flex items-center gap-2 pl-4 font-semibold">
                                                <ModelProviderIcon provider={model.provider} size="sm" />
                                                <Button title={model.alias} variant="link" className="p-0" onClick={() => handleSelectModel(model)}>
                                                    {getDisplayAliasName(model.alias, model.createdBy)}
                                                </Button>
                                                {model.alias === "general" && <Badge>Default</Badge>}
                                            </TableCell>
                                            <TableCell>{getDisplayModelName(model.modelName)}</TableCell>
                                            <TableCell>{PROVIDER_DISPLAY_NAMES[model.provider] || model.provider}</TableCell>
                                            <TableCell className="pr-4 text-right">
                                                <Popover>
                                                    <PopoverTrigger asChild>
                                                        <Button variant="ghost" size="sm" title="Actions">
                                                            <Ellipsis className="h-5 w-5" />
                                                        </Button>
                                                    </PopoverTrigger>
                                                    <PopoverContent align="end" side="bottom" className="w-auto" sideOffset={0}>
                                                        <Menu actions={getRowMenuActions(model)} />
                                                    </PopoverContent>
                                                </Popover>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    ) : (
                        <ModelsOnboardingView title={EMPTY_STATE_TITLE} description={EMPTY_STATE_DESCRIPTION} onAddModel={handleCreateModel} />
                    )}
                </div>

                {/* Pagination */}
                <PaginationControls totalPages={totalPages} currentPage={effectiveCurrentPage} onPageChange={setCurrentPage} />
            </div>
        </div>
    );
};
