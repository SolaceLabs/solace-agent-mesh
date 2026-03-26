import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";

import { Footer, PageContentWrapper, EmptyState, MessageBanner } from "@/lib/components/common";
import { ModelEdit } from "./ModelEdit";
import { getProviderConfig, ALL_PROVIDERS, REDACTED_CREDENTIAL_FIELDS, REDACTED_CREDENTIAL_PLACEHOLDER } from "./modelProviderUtils";
import { fetchModelByAlias, fetchSupportedModelsByProvider, createModelConfig, updateModelConfig, testModelConnection } from "@/lib/api/models/service";
import type { ModelFormData } from "./modelProviderUtils";
import type { ModelConfig } from "@/lib/api/models/types";
import type { TestConnectionResponse } from "@/lib/api/models/service";

/**
 * Build model params and auth config from form data.
 * Shared between save and test connection flows.
 */
function buildModelPayload(data: ModelFormData) {
    // Strip out REDACTED_CREDENTIAL_PLACEHOLDER from credential fields
    // These placeholders are shown during edit to indicate redacted server-stored credentials
    // Converting to empty string prevents overwriting the server-side credential
    REDACTED_CREDENTIAL_FIELDS.forEach(field => {
        if (data[field] === REDACTED_CREDENTIAL_PLACEHOLDER) {
            data[field] = "";
        }
    });

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
    if (data.cache_strategy != null && data.cache_strategy !== "") {
        modelParams.cache_strategy = data.cache_strategy;
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
    if (!modelName.includes("/") && data.provider === "custom") {
        modelName = `openai/${modelName}`;
    }

    return {
        alias: data.alias,
        provider: data.provider,
        modelName,
        apiBase: data.apiBase || null,
        description: data.description || null,
        authType: data.authType,
        authConfig,
        modelParams,
    };
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

    // Test connection state
    const [isTestingConnection, setIsTestingConnection] = useState(false);
    const [testConnectionResult, setTestConnectionResult] = useState<TestConnectionResponse | null>(null);

    // Ref to get current form data from ModelEdit without triggering form submission
    const getFormDataRef = useRef<(() => ModelFormData) | null>(null);

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

    const handleTestConnection = useCallback(async () => {
        if (!getFormDataRef.current) return;

        setIsTestingConnection(true);
        setTestConnectionResult(null);

        try {
            const formData = getFormDataRef.current();
            const payload = buildModelPayload({ ...formData });

            const testPayload = {
                provider: payload.provider,
                modelName: payload.modelName,
                apiBase: payload.apiBase || undefined,
                authType: payload.authType,
                authConfig: payload.authConfig,
                modelParams: payload.modelParams,
                // For editing, include alias so backend can use stored credentials as fallback
                ...(!isNew && modelToEdit ? { alias: modelToEdit.alias } : {}),
            };

            const result = await testModelConnection(testPayload);
            setTestConnectionResult(result);
        } catch (error) {
            const message = error instanceof Error ? error.message : "An unknown error occurred while testing the connection.";
            setTestConnectionResult({ success: false, message });
        } finally {
            setIsTestingConnection(false);
        }
    }, [isNew, modelToEdit]);

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

                <ModelEdit
                    isNew={isNew}
                    modelToEdit={modelToEdit}
                    onSave={handleSave}
                    onValidityChange={setIsFormValid}
                    modelsByProvider={modelsByProvider}
                    availableProviders={ALL_PROVIDERS}
                    onTestConnection={handleTestConnection}
                    isTestingConnection={isTestingConnection}
                    testConnectionResult={testConnectionResult}
                    onDismissTestResult={() => setTestConnectionResult(null)}
                    getFormDataRef={getFormDataRef}
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
