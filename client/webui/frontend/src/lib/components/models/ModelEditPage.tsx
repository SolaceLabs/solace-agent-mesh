import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";

import { Footer, PageContentWrapper, EmptyState, MessageBanner } from "@/lib/components/common";
import { ModelEdit } from "./ModelEdit";
import { ALL_PROVIDERS, buildModelPayload } from "./modelProviderUtils";
import { fetchModelById, createModelConfig, updateModelConfig } from "@/lib/api/models/service";
import { useSupportedModels } from "@/lib/api/models";
import type { ModelFormData } from "./modelProviderUtils";
import type { ModelConfig } from "@/lib/api/models/types";

export const ModelEditPage = () => {
    const navigate = useNavigate();
    const { id: modelId } = useParams<{ id?: string }>();
    const isNew = !modelId;

    const [isLoading, setIsLoading] = useState(false);
    const [isFormValid, setIsFormValid] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [modelToEdit, setModelToEdit] = useState<ModelConfig | null>(null);
    const [modelLoading, setModelLoading] = useState(false);

    // Fetch the specific model being edited (not all models)
    useEffect(() => {
        if (!isNew && modelId) {
            setModelLoading(true);
            fetchModelById(modelId)
                .then(model => {
                    setModelToEdit(model);
                })
                .catch((error: Error) => {
                    console.error(`Error fetching model ${modelId}:`, error);
                    setModelToEdit(null);
                })
                .finally(() => {
                    setModelLoading(false);
                });
        }
    }, [isNew, modelId]);

    // Fetch models for the provider being edited using stored credentials.
    // React Query caches the result so ModelEdit's dropdown open with the same params
    // returns instantly without a duplicate network call.
    const { data: initialModels = [], isLoading: isFetchingModels } = useSupportedModels(!isNew && modelToEdit ? { provider: modelToEdit.provider, modelId: modelToEdit.id } : null);
    const modelsByProvider = modelToEdit ? { [modelToEdit.provider]: initialModels } : {};

    const handleSave = async (data: ModelFormData, dirtyFields?: Partial<Record<string, boolean>>) => {
        setIsLoading(true);
        setErrorMessage(null);

        try {
            const payload = buildModelPayload(data, dirtyFields);

            let createdId: string | undefined;
            if (isNew) {
                const result = await createModelConfig(payload);
                createdId = result.id;
            } else {
                await updateModelConfig(modelToEdit!.id, payload);
            }

            navigate("/agents?tab=models", { state: { highlightModelId: createdId } });
        } catch (error) {
            const message = error instanceof Error ? error.message : "An unknown error occurred while saving the model.";
            setErrorMessage(message);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCancel = () => {
        navigate("/agents?tab=models");
    };

    const title = isNew ? "Create Model" : modelToEdit ? `Edit ${modelToEdit.alias}` : "Model";

    // Loading state for edit mode
    if (!isNew && modelLoading) {
        return <EmptyState variant="loading" title="Loading Model..." />;
    }

    // Loading state while fetching models for the provider
    if (!isNew && isFetchingModels) {
        return <EmptyState variant="loading" title="Loading Models..." />;
    }

    // Not found state for edit mode
    if (!isNew && !modelToEdit) {
        return <EmptyState variant="error" title="Model Not Found" buttons={[{ text: "Go To Models", variant: "default", onClick: () => navigate("/agents?tab=models") }]} />;
    }

    return (
        <div className="flex h-full w-full min-w-4xl flex-col overflow-hidden">
            <Header title={title} breadcrumbs={[{ label: "Agent Mesh", onClick: () => navigate("/agents?tab=models") }, { label: title }]} />

            <PageContentWrapper>
                {errorMessage && <MessageBanner variant="error" message={errorMessage} dismissible onDismiss={() => setErrorMessage(null)} />}

                <ModelEdit isNew={isNew} modelToEdit={modelToEdit} onSave={handleSave} onValidityChange={setIsFormValid} modelsByProvider={modelsByProvider} availableProviders={ALL_PROVIDERS} />
            </PageContentWrapper>

            <Footer>
                <Button variant="outline" title="Cancel" onClick={handleCancel} disabled={isLoading}>
                    Cancel
                </Button>
                <Button type="submit" form="model-form" disabled={!isFormValid || isLoading} title={isNew ? "Add Model" : "Save Model"}>
                    {isLoading ? "Saving..." : isNew ? "Add" : "Save"}
                </Button>
            </Footer>
        </div>
    );
};
