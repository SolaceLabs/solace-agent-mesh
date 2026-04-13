import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";

import { Footer, PageContentWrapper, EmptyState, MessageBanner, ConfirmationDialog } from "@/lib/components/common";
import { ModelEdit } from "./ModelEdit";
import { ALL_PROVIDERS, buildModelPayload } from "./modelProviderUtils";
import { fetchModelById, createModelConfig, updateModelConfig, testModelConnection } from "@/lib/api/models/service";
import { useSupportedModels } from "@/lib/api/models";
import { getErrorMessage } from "@/lib/utils/api";
import type { ModelFormData } from "./modelProviderUtils";
import type { ModelConfig } from "@/lib/api/models/types";

export const ModelEditPage = () => {
    const navigate = useNavigate();
    const { id: modelId } = useParams<{ id?: string }>();
    const isNew = !modelId;

    const [isLoading, setIsLoading] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [modelToEdit, setModelToEdit] = useState<ModelConfig | null>(null);
    const [modelLoading, setModelLoading] = useState(false);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [showSaveFailedDialog, setShowSaveFailedDialog] = useState(false);
    const [saveFailMessage, setSaveFailMessage] = useState("");
    const pendingPayloadRef = useRef<ReturnType<typeof buildModelPayload> | null>(null);

    // Fetch the specific model being edited (not all models)
    useEffect(() => {
        if (!isNew && modelId) {
            setModelLoading(true);
            setFetchError(null);
            fetchModelById(modelId)
                .then(model => {
                    setModelToEdit(model);
                })
                .catch((error: unknown) => {
                    setModelToEdit(null);
                    setFetchError(getErrorMessage(error, "Failed to load model."));
                })
                .finally(() => {
                    setModelLoading(false);
                });
        }
    }, [isNew, modelId]);

    // Fetch models for the provider being edited using stored credentials.
    // React Query caches the result so ModelEdit's dropdown open with the same params
    // returns instantly without a duplicate network call.
    const { data: initialModels = [], isLoading: isFetchingModels } = useSupportedModels(!isNew && modelToEdit && modelToEdit.provider ? { provider: modelToEdit.provider, modelId: modelToEdit.id } : null);
    const modelsByProvider = modelToEdit?.provider ? { [modelToEdit.provider]: initialModels } : {};

    const performSave = useCallback(
        async (payload: ReturnType<typeof buildModelPayload>) => {
            setIsLoading(true);
            try {
                let createdId: string | undefined;
                if (isNew) {
                    const result = await createModelConfig(payload);
                    createdId = result.id;
                } else {
                    await updateModelConfig(modelToEdit!.id, payload);
                }
                navigate("/agents?tab=models", { state: { highlightModelId: createdId } });
            } catch (error) {
                setErrorMessage(getErrorMessage(error, "An unknown error occurred while saving the model."));
            } finally {
                setIsLoading(false);
            }
        },
        [isNew, modelToEdit, navigate]
    );

    const handleSaveAnyway = useCallback(async () => {
        setShowSaveFailedDialog(false);
        await performSave(pendingPayloadRef.current!);
    }, [performSave]);

    const handleSave = async (data: ModelFormData, dirtyFields?: Partial<Record<string, boolean>>) => {
        setIsLoading(true);
        setErrorMessage(null);

        const payload = buildModelPayload(data, dirtyFields);
        pendingPayloadRef.current = payload;

        // Step 1: Test connection silently
        const testPayload = {
            provider: payload.provider,
            modelName: payload.modelName,
            apiBase: payload.apiBase || undefined,
            authConfig: payload.authConfig,
            modelParams: payload.modelParams,
            ...(!isNew && modelToEdit?.id ? { modelId: modelToEdit.id } : {}),
        };

        let testPassed = false;
        try {
            const result = await testModelConnection(testPayload);
            testPassed = result.success;
            if (!testPassed) setSaveFailMessage(result.message);
        } catch (error) {
            setSaveFailMessage(getErrorMessage(error, "Connection test failed."));
        }

        if (!testPassed) {
            setShowSaveFailedDialog(true);
            setIsLoading(false);
            return;
        }

        // Step 2: Test passed — save directly
        await performSave(payload);
    };

    const handleCancel = () => {
        navigate("/agents?tab=models");
    };

    const editTitle = modelToEdit ? `Edit ${modelToEdit.alias}` : "Model";
    const title = isNew ? "Add Model" : editTitle;

    // Loading state for edit mode
    if (!isNew && modelLoading) {
        return <EmptyState variant="loading" title="Loading Model..." />;
    }

    // Loading state while fetching models for the provider
    if (!isNew && isFetchingModels) {
        return <EmptyState variant="loading" title="Loading Models..." />;
    }

    // Error state for edit mode
    if (!isNew && fetchError) {
        return <EmptyState variant="error" title={`Error loading model: ${fetchError}`} buttons={[{ text: "Go To Models", variant: "default", onClick: () => navigate("/agents?tab=models") }]} />;
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
                <ModelEdit isNew={isNew} modelToEdit={modelToEdit} onSave={handleSave} modelsByProvider={modelsByProvider} availableProviders={ALL_PROVIDERS} />
            </PageContentWrapper>

            <ConfirmationDialog
                open={showSaveFailedDialog}
                onOpenChange={setShowSaveFailedDialog}
                title={isNew ? "Add Model Configuration Failed" : "Save Model Configuration Failed"}
                content={
                    <div className="space-y-3">
                        <MessageBanner variant="error" message={saveFailMessage} />
                        <p className="text-sm text-(--secondary-text-wMain)">Would you like to save anyway or go back to fix the issue?</p>
                    </div>
                }
                actionLabels={{ cancel: "Go Back", confirm: "Save Anyway" }}
                onConfirm={handleSaveAnyway}
                isLoading={isLoading}
            />

            <Footer>
                <Button variant="ghost" title="Cancel" onClick={handleCancel} disabled={isLoading}>
                    Cancel
                </Button>
                <Button type="submit" form="model-form" disabled={isLoading} title={isNew ? "Add Model" : "Save Model"}>
                    {isLoading ? "Saving..." : isNew ? "Add" : "Save"}
                </Button>
            </Footer>
        </div>
    );
};
