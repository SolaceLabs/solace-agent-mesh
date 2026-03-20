import { useMemo, useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";

import { Footer, PageContentWrapper, EmptyState } from "@/lib/components/common";
import { ModelEdit } from "./ModelEdit";
import { getProviderConfig, getAllProviders } from "./modelProviderUtils";
import { fetchModelByAlias, fetchSupportedModelsByProvider, createModelConfig, updateModelConfig } from "@/lib/api/models/service";
import type { ModelProvider } from "./modelProviderUtils";
import type { ModelConfig } from "@/lib/api/models/types";

interface FormData {
    alias: string;
    description: string;
    provider: string;
    modelName: string;
    apiBase?: string;
    authType: string;
    apiKey?: string;
    clientId?: string;
    clientSecret?: string;
    tokenUrl?: string;
    oauthScope?: string;
    oauthTokenRefreshBufferSeconds?: string;
    awsAccessKeyId?: string;
    awsSecretAccessKey?: string;
    awsSessionToken?: string;
    gcpServiceAccountJson?: string;
    temperature?: string;
    maxTokens?: string;
    customParams?: Array<{ key: string; value: string }>;
    [key: string]: unknown;
}

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

    // Use hardcoded available providers
    const availableProviders = useMemo((): ModelProvider[] => {
        return getAllProviders();
    }, []);

    // Don't fetch models when provider changes
    // Models are only fetched when the Model Name dropdown opens (in ModelEdit)
    // at that point we have authentication credentials filled in
    const handleProviderChange = async () => {
        // No-op: models will be fetched on-demand when dropdown opens
    };

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

    const handleSave = async (data: FormData) => {
        setIsLoading(true);
        setErrorMessage(null);

        try {
            const providerConfig = getProviderConfig(data.provider);

            // Collect model_params from provider-specific fields
            const modelParams: Record<string, unknown> = {};
            for (const field of providerConfig.fields) {
                if (data[field.name] != null && data[field.name] !== "") {
                    const value = field.type === "number" ? Number(data[field.name]) : data[field.name];
                    modelParams[field.name] = value;
                }
            }

            // Add common model params
            if (data.temperature != null && data.temperature !== "") {
                modelParams.temperature = Number(data.temperature);
            }
            if (data.maxTokens != null && data.maxTokens !== "") {
                modelParams.max_tokens = Number(data.maxTokens);
            }

            // Add custom parameters
            if (data.customParams && Array.isArray(data.customParams)) {
                data.customParams.forEach((param: { key: string; value: string }) => {
                    if (param.key.trim()) {
                        modelParams[param.key] = param.value;
                    }
                });
            }

            // Build auth config
            // When editing, only include credential fields if they are provided (not empty)
            // This preserves existing server-side credentials if user doesn't change them
            let authConfig: Record<string, unknown> = {};
            if (data.authType === "apikey") {
                authConfig = { type: "apikey" };
                if (data.apiKey) {
                    authConfig.api_key = data.apiKey;
                }
            } else if (data.authType === "oauth2") {
                authConfig = { type: "oauth2" };
                if (data.clientId) {
                    authConfig.client_id = data.clientId;
                }
                if (data.clientSecret) {
                    authConfig.client_secret = data.clientSecret;
                }
                if (data.tokenUrl) {
                    authConfig.token_url = data.tokenUrl;
                }
                if (data.oauthScope) {
                    authConfig.scope = data.oauthScope;
                }
                if (data.oauthTokenRefreshBufferSeconds) {
                    authConfig.token_refresh_buffer_seconds = Number(data.oauthTokenRefreshBufferSeconds);
                }
            } else if (data.authType === "aws_iam") {
                authConfig = { type: "aws_iam" };
                if (data.awsAccessKeyId) {
                    authConfig.aws_access_key_id = data.awsAccessKeyId;
                }
                if (data.awsSecretAccessKey) {
                    authConfig.aws_secret_access_key = data.awsSecretAccessKey;
                }
                if (data.awsSessionToken) {
                    authConfig.aws_session_token = data.awsSessionToken;
                }
            } else if (data.authType === "gcp_service_account") {
                authConfig = { type: "gcp_service_account" };
                if (data.gcpServiceAccountJson) {
                    authConfig.service_account_json = data.gcpServiceAccountJson;
                }
            } else {
                authConfig = { type: "none" };
            }

            // Format model name with provider prefix if needed
            let modelName = data.modelName;
            if (!modelName.includes("/") && data.provider === "openai_compatible") {
                modelName = `openai/${modelName}`;
            }

            const payload = {
                alias: data.alias,
                provider: data.provider,
                modelName,
                apiBase: data.apiBase || null,
                description: data.description || null,
                authType: data.authType,
                authConfig,
                modelParams,
            };

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
                {errorMessage && <div className="mb-4 rounded bg-red-100 p-3 text-sm text-red-700">{errorMessage}</div>}

                <ModelEdit
                    isNew={isNew}
                    modelToEdit={modelToEdit}
                    onSave={handleSave}
                    onValidityChange={setIsFormValid}
                    onDirtyStateChange={() => {}}
                    modelsByProvider={modelsByProvider}
                    availableProviders={availableProviders}
                    onProviderChange={handleProviderChange}
                />
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
