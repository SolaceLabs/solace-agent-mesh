import React, { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

import { Ellipsis, AlertTriangle } from "lucide-react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    Button,
    Badge,
    Menu,
    Popover,
    PopoverContent,
    PopoverTrigger,
    SortableTableHead,
    useSortableTable,
    Tooltip,
    TooltipTrigger,
    TooltipContent,
    type MenuAction,
} from "@/lib/components/ui";
import { PaginationControls, EmptyState, OnboardingBanner, OnboardingView } from "@/lib/components/common";
import { useChatContext } from "@/lib/hooks";

import { useModelConfigs, useDeleteModel } from "@/lib/api/models";
import type { ModelConfig } from "@/lib/api/models/types";
import { ModelProviderIcon } from "./ModelProviderIcon";
import { ModelDeleteDialog } from "./ModelDeleteDialog";
import { getProviderDisplayName, getDisplayModelName, getDisplayAliasName, DEFAULT_MODEL_ALIASES, isModelConfigured } from "./common";

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
    const { addNotification } = useChatContext();
    const { data: modelConfigs = [], isLoading: modelConfigsLoading, error: modelConfigsErrorObj } = useModelConfigs();
    const deleteModel = useDeleteModel();
    const [currentPage, setCurrentPage] = useState<number>(1);
    const [modelToDelete, setModelToDelete] = useState<ModelConfig | null>(null);
    const [highlightedModelId, setHighlightedModelId] = useState<string | null>(null);
    const highlightedRowRef = useRef<HTMLTableRowElement>(null);
    const { sortedData: sortedModels, sortKey, sortDir, handleSort } = useSortableTable(modelConfigs, ["alias", "modelName", "provider"]);

    // Reset to first page whenever sort changes
    useEffect(() => {
        setCurrentPage(1);
    }, [sortKey, sortDir]);

    // Check if we're coming back from creating a new model
    const locationState = location.state as { highlightModelId?: string } | null;
    useEffect(() => {
        if (locationState?.highlightModelId) {
            setHighlightedModelId(locationState.highlightModelId);
            addNotification("Model Added", "success");

            // Clear the location state to prevent re-triggering on refresh
            navigate(location.pathname + location.search, { replace: true });

            // Auto-fade highlight after 4 seconds
            const highlightTimer = setTimeout(() => {
                setHighlightedModelId(null);
            }, 4000);

            return () => {
                clearTimeout(highlightTimer);
            };
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [locationState?.highlightModelId]);

    // Scroll highlighted row into view
    useEffect(() => {
        if (highlightedRowRef.current) {
            highlightedRowRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [highlightedModelId]);

    const modelConfigsError = modelConfigsErrorObj ? (modelConfigsErrorObj instanceof Error ? modelConfigsErrorObj.message : "Failed to load models") : null;

    const hasModels = modelConfigs && modelConfigs.length > 0;

    // Client-side pagination (sorting is handled by useSortableTable)
    const itemsPerPage = 20;
    const totalPages = Math.ceil(sortedModels.length / itemsPerPage);
    const effectiveCurrentPage = Math.min(currentPage, Math.max(totalPages, 1));
    const startIndex = (effectiveCurrentPage - 1) * itemsPerPage;
    const currentModels = sortedModels.slice(startIndex, startIndex + itemsPerPage);

    const handleSelectModel = (model: ModelConfig) => {
        navigate(`/models/${model.id}`);
    };

    const handleCreateModel = () => {
        navigate("/models/new/edit");
    };

    const handleEditModel = (model: ModelConfig) => {
        navigate(`/models/${model.id}/edit`);
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
            onClick: () => setModelToDelete(model),
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
                                        <SortableTableHead column="alias" currentSortKey={sortKey} sortDir={sortDir} onSort={handleSort} className="pl-4">
                                            Name
                                        </SortableTableHead>
                                        <SortableTableHead column="modelName" currentSortKey={sortKey} sortDir={sortDir} onSort={handleSort}>
                                            Model
                                        </SortableTableHead>
                                        <SortableTableHead column="provider" currentSortKey={sortKey} sortDir={sortDir} onSort={handleSort}>
                                            Model Provider
                                        </SortableTableHead>
                                        <TableHead className="w-12"></TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {currentModels.map(model => (
                                        <TableRow
                                            key={model.id}
                                            ref={highlightedModelId === model.id ? highlightedRowRef : null}
                                            className={cn("transition-colors duration-500", highlightedModelId === model.id ? "bg-(--success-w10)" : "hover:bg-(--primary-w10)")}
                                        >
                                            <TableCell className="flex items-center gap-2 pl-4 font-semibold">
                                                <ModelProviderIcon provider={model.provider} size="sm" />
                                                <Button title={model.alias} variant="link" className="p-0" onClick={() => handleSelectModel(model)}>
                                                    {getDisplayAliasName(model.alias, model.createdBy)}
                                                </Button>
                                                {DEFAULT_MODEL_ALIASES.includes(model.alias) && (
                                                    <Badge
                                                        tooltip={
                                                            model.alias === "general" ? "Used by all built-in AI features. This cannot be deleted but can be modified." : "Used for the Orchestrator Agent. This cannot be deleted but can be modified."
                                                        }
                                                        tooltipSide="right"
                                                    >
                                                        Default
                                                    </Badge>
                                                )}
                                                {DEFAULT_MODEL_ALIASES.includes(model.alias) && !isModelConfigured(model) && (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <AlertTriangle className="h-4 w-4 shrink-0 cursor-default text-(--warning-wMain)" />
                                                        </TooltipTrigger>
                                                        <TooltipContent>
                                                            <p>This model needs connection details configured before it can be used.</p>
                                                        </TooltipContent>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                            <TableCell>{getDisplayModelName(model.modelName) || <span className="text-(--secondary-text-wMain) italic">Not configured</span>}</TableCell>
                                            <TableCell>{getProviderDisplayName(model.provider) ?? <span className="text-(--secondary-text-wMain) italic">Not configured</span>}</TableCell>
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
                        <OnboardingView title={EMPTY_STATE_TITLE} description={EMPTY_STATE_DESCRIPTION} learnMoreText={MODELS_LEARN_MORE_TEXT} learnMoreHref={MODELS_URL} actionButton={{ text: "Add Model", onClick: handleCreateModel }} />
                    )}
                </div>

                {/* Pagination */}
                <PaginationControls totalPages={totalPages} currentPage={effectiveCurrentPage} onPageChange={setCurrentPage} />
            </div>

            {modelToDelete && (
                <ModelDeleteDialog
                    open={!!modelToDelete}
                    onOpenChange={open => {
                        if (!open) setModelToDelete(null);
                    }}
                    onConfirm={async () => {
                        await deleteModel.mutateAsync(modelToDelete.id);
                        setModelToDelete(null);
                    }}
                    isLoading={deleteModel.isPending}
                    modelId={modelToDelete.id}
                    modelAlias={modelToDelete.alias}
                />
            )}
        </div>
    );
};
