import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";

import { Footer, PageContentWrapper, EmptyState, MessageBanner } from "@/lib/components/common";
import { ModelEdit } from "./ModelEdit";
import { ALL_PROVIDERS, buildModelPayload } from "./modelProviderUtils";
import { fetchModelByAlias, fetchSupportedModelsByProvider, createModelConfig, updateModelConfig } from "@/lib/api/models/service";
import type { ModelFormData } from "./modelProviderUtils";
import type { ModelConfig } from "@/lib/api/models/types";

export const ModelEditPage = () => {
    const navigate = useNavigate();
    const { alias: modelAlias } = useParams<{ alias?: string }>();
    const isNew = !modelAlias;

    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingModels, setIsFetchingModels] = useState(false);
    const [isFormValid, setIsFormValid] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [modelsByProvider, setModelsByProvider] = useState<Record<string, Array<{ id: string; label: string }>>>({});
    const [modelToEdit, setModelToEdit] = useState<ModelConfig | null>(null);
    const [modelLoading, setModelLoading] = useState(false);
    const fetchedRef = useRef<Set<string>>(new Set()); // Track what we've already fetched

    // Fetch the specific model being edited (not all models)
    useEffect(() => {
        if (!isNew && modelAlias) {
            setModelLoading(true);
            fetchModelByAlias(modelAlias)
                .then(model => {
                    setModelToEdit(model);
                })
                .catch((error: Error) => {
                    console.error(`Error fetching model ${modelAlias}:`, error);
                    setModelToEdit(null);
                })
                .finally(() => {
                    setModelLoading(false);
                });
        }
    }, [isNew, modelAlias]);

    // When editing an existing model, fetch models for its provider using stored credentials
    useEffect(() => {
        if (!isNew && modelToEdit) {
            const cacheKey = `${modelToEdit.provider}:${modelToEdit.alias}`;

            // Skip if we've already fetched this exact provider:alias combo
            if (fetchedRef.current.has(cacheKey)) {
                return;
            }

            fetchedRef.current.add(cacheKey);
            setIsFetchingModels(true);

            fetchSupportedModelsByProvider(modelToEdit.provider, modelToEdit.alias)
                .then(models => {
                    setModelsByProvider(prev => ({
                        ...prev,
                        [modelToEdit.provider]: models,
                    }));
                })
                .catch((error: Error) => {
                    // TODO: Surface a subtle UI notification so the user knows model fetch failed
                    // and can fall back to manual entry. Discuss UX approach with design team.
                    console.error(`Error fetching models for provider ${modelToEdit.provider}:`, error);
                    setModelsByProvider(prev => ({
                        ...prev,
                        [modelToEdit.provider]: [],
                    }));
                })
                .finally(() => {
                    setIsFetchingModels(false);
                });
        }
    }, [modelToEdit, isNew]);

    const handleSave = async (data: ModelFormData) => {
        setIsLoading(true);
        setErrorMessage(null);

        try {
            const payload = buildModelPayload(data);

            let createdAlias: string | undefined;
            if (isNew) {
                const result = await createModelConfig(payload);
                createdAlias = result.alias;
            } else {
                await updateModelConfig(modelToEdit!.alias, payload);
            }

            navigate("/agents?tab=models", { state: { highlightModelAlias: createdAlias } });
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
