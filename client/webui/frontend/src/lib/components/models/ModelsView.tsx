import React, { useState } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Button, Badge } from "@/lib/components/ui";
import { PaginationControls, EmptyState, OnboardingBanner } from "@/lib/components/common";

import { useModelConfigs } from "@/lib/api/models";
import type { ModelConfig } from "@/lib/api/models/types";
import { ModelsOnboardingView } from "./ModelsOnboardingView";
import { ModelProviderIcon } from "./ModelProviderIcon";

const MODELS_STORAGE_KEY = "sam-models-onboarding-dismissed";
const MODELS_HEADER = "Your Models Are Now Accessible to Your Team";
const MODELS_DESCRIPTION =
    "Existing models from your local backend configuration have been imported here and are now accessible for anyone in your organization. Going forward, changes you make in this UI will take precedence over your shared config file.";
const MODELS_LEARN_MORE_TEXT = "Learn about managing models";
const MODELS_URL = "#"; // TODO: Add documentation URL

const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
    anthropic: "Anthropic",
    openai: "OpenAI",
    openai_compatible: "OpenAI Compatible",
    google_ai_studio: "Google AI Studio",
    vertex_ai: "Google Vertex AI",
    azure_openai: "Azure OpenAI",
    bedrock: "Amazon Bedrock",
    ollama: "Ollama",
    custom: "Custom",
};

const EMPTY_STATE_TITLE = "Match AI Models to Your Team's Workflows";
const EMPTY_STATE_DESCRIPTION =
    "Different models specialize in different use cases. Organize your models by use case and assign to agents based on what the agent needs. Start with our suggested names or create your own. The 'General' model is required but you can customize everything else to fit your workflow.";

export const ModelsView: React.FC = () => {
    const { data: modelConfigs = [], isLoading: modelConfigsLoading, error: modelConfigsErrorObj } = useModelConfigs();
    const [currentPage, setCurrentPage] = useState<number>(1);

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
        // TODO: Navigate to model details page
        console.log("Selected model:", model.alias);
    };

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
                                        <TableHead className="font-semibold">
                                            <div className="pl-4">Name</div>
                                        </TableHead>
                                        <TableHead className="font-semibold">Model</TableHead>
                                        <TableHead className="font-semibold">Model Provider</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {currentModels.map(model => (
                                        <TableRow key={model.id} className="hover:bg-(--secondary-w10)">
                                            <TableCell className="flex items-center gap-2 pl-4 font-semibold">
                                                <ModelProviderIcon provider={model.provider} size="sm" />
                                                <Button title={model.alias} variant="link" className="p-0" onClick={() => handleSelectModel(model)}>
                                                    {model.alias}
                                                </Button>
                                                {model.alias === "general" && <Badge>Default</Badge>}
                                            </TableCell>
                                            <TableCell>{model.modelName}</TableCell>
                                            <TableCell>{PROVIDER_DISPLAY_NAMES[model.provider] || model.provider}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    ) : (
                        <ModelsOnboardingView title={EMPTY_STATE_TITLE} description={EMPTY_STATE_DESCRIPTION} />
                    )}
                </div>

                {/* Pagination */}
                <PaginationControls totalPages={totalPages} currentPage={effectiveCurrentPage} onPageChange={setCurrentPage} />
            </div>
        </div>
    );
};
