import { useEffect, useState, useCallback, useRef } from "react";
import { useForm, FormProvider, Controller } from "react-hook-form";
import { Input, Textarea, Button } from "@/lib/components/ui";
import { Plus } from "lucide-react";

import type { ModelConfig } from "@/lib/api/models";
import { PageLabel, PageSection, PageLabelWithValue, ErrorLabel } from "../common/PageCommon";
import { getProviderConfig, AUTH_FIELDS, COMMON_MODEL_PARAMS, type AuthType, type ProviderField, type SupportedModel, type ModelProvider } from "./modelProviderUtils";
import { fetchSupportedModelsByProvider } from "@/lib/api/models/service";
import { ProviderSelect } from "./ProviderSelect";
import { DropDown } from "../common/DropDown";
import { KeyValuePairList } from "../common/KeyValuePairList";

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
    temperature?: string;
    maxTokens?: string;
    customParams?: Array<{ key: string; value: string }>;
    [key: string]: unknown;
}

interface ModelEditProps {
    isNew: boolean;
    modelToEdit: ModelConfig | null;
    onSave: (data: FormData) => Promise<void>;
    onValidityChange: (isValid: boolean) => void;
    onDirtyStateChange: (isDirty: boolean) => void;
    modelsByProvider?: Record<string, Array<{ id: string; label: string }>>;
    availableProviders?: ModelProvider[];
    onProviderChange?: (provider: string) => Promise<void>;
}

export const ModelEdit = ({ isNew, modelToEdit, onSave, onValidityChange, onDirtyStateChange, modelsByProvider = {}, availableProviders = [], onProviderChange }: ModelEditProps) => {
    const methods = useForm<FormData>({
        mode: "onSubmit",
        reValidateMode: "onChange",
        defaultValues: {
            customParams: [],
        },
    });

    const [providerConfig, setProviderConfig] = useState<ReturnType<typeof getProviderConfig> | null>(null);
    const [dynamicModels, setDynamicModels] = useState<SupportedModel[]>([]);
    const hasInitializedFromModelRef = useRef(false);

    const {
        register,
        control,
        formState: { errors, isDirty, isValid },
        handleSubmit,
        watch,
        setValue,
        resetField,
        getValues,
    } = methods;

    const handleAddCustomParam = useCallback(() => {
        const currentParams = getValues("customParams") ?? [];
        setValue("customParams", [...currentParams, { key: "", value: "" }]);
    }, [getValues, setValue]);

    const selectedProvider = watch("provider");
    const selectedAuthType = watch("authType");
    const apiBase = watch("apiBase");
    const apiKey = watch("apiKey");

    useEffect(() => {
        onDirtyStateChange(isDirty);
    }, [isDirty, onDirtyStateChange]);

    useEffect(() => {
        onValidityChange(isValid);
    }, [isValid, onValidityChange]);

    // Update provider config and reset dynamic fields when provider changes
    useEffect(() => {
        if (selectedProvider) {
            const config = getProviderConfig(selectedProvider);
            setProviderConfig(config);
            setDynamicModels([]); // Reset dynamic models when provider changes

            // Skip resetting fields on initial model load; only reset when user manually changes provider
            if (hasInitializedFromModelRef.current && !isNew && modelToEdit && modelToEdit.provider === selectedProvider) {
                hasInitializedFromModelRef.current = false; // Clear flag so future changes will reset
                // Still fetch models for the provider
                onProviderChange?.(selectedProvider);
                return;
            }

            // Fetch models for this provider if callback provided
            onProviderChange?.(selectedProvider);

            // Reset model-related fields (keep only alias and description)
            resetField("modelName");
            resetField("apiBase");

            // Reset provider-specific and auth fields when provider changes
            config.fields.forEach((field: ProviderField) => {
                resetField(field.name);
            });
            // Reset all auth type fields
            Object.values(AUTH_FIELDS).forEach(fields => {
                (fields as ProviderField[]).forEach((field: ProviderField) => {
                    resetField(field.name);
                });
            });

            // Reset common model parameters
            resetField("temperature");
            resetField("maxTokens");

            // Set default auth type to first allowed type for this provider
            setValue("authType", config.allowedAuthTypes[0]);
            // Reset custom params
            resetField("customParams");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedProvider, isNew, modelToEdit]);

    // Fetch models when dropdown opens
    // For editing: use cached models from database (via modelsByProvider)
    // For creating: fetch from provider API using credentials from form
    const handleModelDropdownOpen = useCallback(async () => {
        if (!selectedProvider) return;

        // For editing, use cached models from modelsByProvider (fetched server-side with stored credentials)
        if (!isNew && modelsByProvider[selectedProvider]) {
            setDynamicModels(modelsByProvider[selectedProvider]);
            return;
        }

        // For creating new models, fetch from provider using form credentials
        if (isNew) {
            const authType = selectedAuthType || "apikey";

            // Collect provider-specific model params from form
            const currentProviderConfig = providerConfig || getProviderConfig(selectedProvider);
            const modelParams: Record<string, unknown> = {};
            for (const field of currentProviderConfig.fields) {
                const val = getValues(field.name);
                if (val != null && val !== "") {
                    modelParams[field.name] = val;
                }
            }

            try {
                const models = await fetchSupportedModelsByProvider(selectedProvider, undefined, {
                    apiBase: apiBase || undefined,
                    authType,
                    apiKey: authType === "apikey" ? apiKey : undefined,
                    clientId: authType === "oauth2" ? (getValues("clientId") as string) : undefined,
                    clientSecret: authType === "oauth2" ? (getValues("clientSecret") as string) : undefined,
                    tokenUrl: authType === "oauth2" ? (getValues("tokenUrl") as string) : undefined,
                    awsAccessKeyId: authType === "aws_iam" ? (getValues("awsAccessKeyId") as string) : undefined,
                    awsSecretAccessKey: authType === "aws_iam" ? (getValues("awsSecretAccessKey") as string) : undefined,
                    awsSessionToken: authType === "aws_iam" ? (getValues("awsSessionToken") as string) : undefined,
                    gcpServiceAccountJson: authType === "gcp_service_account" ? (getValues("gcpServiceAccountJson") as string) : undefined,
                    modelParams: Object.keys(modelParams).length > 0 ? modelParams : undefined,
                });
                setDynamicModels(models);
            } catch (error) {
                console.error("Error fetching models:", error);
                setDynamicModels([]);
            }
        }
    }, [selectedProvider, isNew, apiBase, apiKey, selectedAuthType, modelsByProvider, getValues, providerConfig]);

    useEffect(() => {
        if (!isNew && modelToEdit) {
            // Mark that we're initializing from modelToEdit BEFORE setting provider
            // so the provider change effect doesn't reset our fields
            hasInitializedFromModelRef.current = true;

            setValue("alias", modelToEdit.alias);
            setValue("provider", modelToEdit.provider);

            // Strip provider prefix from model name for editing
            // e.g., "openai/bedrock-claude-4-5-haiku" → "bedrock-claude-4-5-haiku"
            let modelName = modelToEdit.modelName;
            if (modelToEdit.provider === "openai_compatible" && modelName?.startsWith("openai/")) {
                modelName = modelName.substring(7);
            }

            setValue("modelName", modelName);
            setValue("apiBase", modelToEdit.apiBase || "");
            setValue("authType", modelToEdit.authType || "apikey");
            setValue("description", modelToEdit.description || "");

            // Populate provider-specific fields and custom params from modelParams
            if (modelToEdit.modelParams) {
                const config = getProviderConfig(modelToEdit.provider);
                const knownParamNames = new Set<string>();

                // Add provider-specific fields to known params
                config.fields.forEach((field: ProviderField) => {
                    knownParamNames.add(field.name);
                    if (field.name in modelToEdit.modelParams) {
                        setValue(field.name, modelToEdit.modelParams[field.name]);
                    }
                });

                // Populate common model params
                knownParamNames.add("temperature");
                knownParamNames.add("maxTokens");
                knownParamNames.add("max_tokens");

                if ("temperature" in modelToEdit.modelParams) {
                    setValue("temperature", String(modelToEdit.modelParams.temperature));
                }
                if ("max_tokens" in modelToEdit.modelParams) {
                    setValue("maxTokens", String(modelToEdit.modelParams.max_tokens));
                }

                // Extract custom parameters (anything not in known params)
                const customParamsArray = Object.entries(modelToEdit.modelParams)
                    .filter(([key]) => !knownParamNames.has(key))
                    .map(([key, value]) => ({ key, value: String(value) }));
                if (customParamsArray.length > 0) {
                    setValue("customParams", customParamsArray);
                }
            }
        } else if (isNew) {
            // Reset flag when creating new
            hasInitializedFromModelRef.current = false;
        }
    }, [modelToEdit, isNew, setValue]);

    const providers = availableProviders;

    // Helper function to render a single field
    const renderField = (field: ProviderField) => {
        // For auth fields during edit, make them optional (credentials are stored server-side)
        // Only auth credential fields are truly optional;
        // structural fields (clientId, tokenUrl, etc.) remain required for setup
        const isAuthCredentialField = field.storageTarget === "auth" && ["apiKey", "clientSecret", "awsSecretAccessKey", "awsSessionToken", "gcpServiceAccountJson"].includes(field.name);
        const isRequiredField = field.required && (!isAuthCredentialField || isNew);

        return (
            <PageLabelWithValue key={field.name}>
                <PageLabel required={isRequiredField}>{field.label}</PageLabel>
                {field.type === "textarea" ? (
                    <Textarea
                        rows={6}
                        placeholder={field.placeholder}
                        {...register(field.name, {
                            required: isRequiredField ? `${field.label} is required` : false,
                        })}
                        aria-invalid={!!errors[field.name]}
                    />
                ) : (
                    <Input
                        type={field.type === "password" ? "password" : field.type === "number" ? "number" : "text"}
                        inputMode={field.type === "number" ? "decimal" : undefined}
                        placeholder={field.placeholder}
                        step={field.type === "number" ? field.step : undefined}
                        {...register(field.name, {
                            required: isRequiredField ? `${field.label} is required` : false,
                            ...(field.type === "number" &&
                                field.min !== undefined && {
                                    min: {
                                        value: field.min,
                                        message: `${field.label} must be at least ${field.min}`,
                                    },
                                }),
                            ...(field.type === "number" &&
                                field.max !== undefined && {
                                    max: {
                                        value: field.max,
                                        message: `${field.label} must not exceed ${field.max}`,
                                    },
                                }),
                        })}
                        aria-invalid={!!errors[field.name]}
                    />
                )}
                {field.helpText && <div className="text-secondary-foreground text-xs">{field.helpText}</div>}
                {errors[field.name] && <ErrorLabel>{getErrorMessage(errors[field.name])}</ErrorLabel>}
            </PageLabelWithValue>
        );
    };

    const onFormSubmit = async (data: FormData) => {
        await onSave(data);
    };

    // Helper to safely extract error message from react-hook-form errors
    const getErrorMessage = (error: unknown): string | undefined => {
        if (!error || typeof error !== "object") return undefined;
        const errObj = error as Record<string, unknown>;
        if (typeof errObj.message === "string") return errObj.message;
        return undefined;
    };

    // Map auth type labels
    const authTypeLabels: Record<AuthType, string> = {
        apikey: "API Key",
        oauth2: "OAuth",
        none: "None",
        aws_iam: "AWS IAM",
        gcp_service_account: "GCP Service Account",
    };

    return (
        <FormProvider {...methods}>
            <div>
                <form id="model-form" onSubmit={handleSubmit(onFormSubmit)}>
                    <PageSection className="gap-6">
                        {/* Display Name / Alias - Always Visible */}
                        <PageLabelWithValue>
                            <PageLabel required>Display Name</PageLabel>
                            <Input
                                {...register("alias", { required: "Display name is required" })}
                                aria-invalid={!!errors.alias}
                                disabled={!isNew && modelToEdit?.alias.toLowerCase() === "general"}
                                title={!isNew && modelToEdit?.alias.toLowerCase() === "general" ? "The General model's name cannot be changed" : ""}
                            />
                            <div className="text-secondary-foreground text-xs">
                                Provide a short, descriptive name for this model for others in your organization to reference. Example: "Analysis".
                                {!isNew && modelToEdit?.alias.toLowerCase() === "general" && <div className="mt-1 text-xs text-orange-600">The General model's name cannot be changed.</div>}
                            </div>
                            {errors.alias && <ErrorLabel>{getErrorMessage(errors.alias)}</ErrorLabel>}
                        </PageLabelWithValue>

                        {/* Description - Always Visible */}
                        <PageLabelWithValue>
                            <PageLabel required>Description</PageLabel>
                            <Textarea {...register("description", { required: "Description is required" })} rows={4} maxLength={1001} aria-invalid={!!errors.description} />
                            <div className="text-secondary-foreground text-xs">Describe types of tasks this model is suitable or not suitable for.</div>
                            {errors.description && <ErrorLabel>{getErrorMessage(errors.description)}</ErrorLabel>}
                        </PageLabelWithValue>

                        {/* Provider Dropdown - Always Visible */}
                        <PageLabelWithValue>
                            <PageLabel required>Model Provider</PageLabel>
                            <Controller
                                name="provider"
                                control={control}
                                rules={{ required: "Provider is required" }}
                                render={({ field }) => <ProviderSelect value={field.value} onValueChange={field.onChange} providers={providers} invalid={!!errors.provider} />}
                            />
                            {errors.provider && <ErrorLabel>{getErrorMessage(errors.provider)}</ErrorLabel>}
                        </PageLabelWithValue>

                        {/* Provider-specific fields only shown after provider selection */}
                        {selectedProvider && providerConfig && (
                            <>
                                {/* API Base (conditional) */}
                                {providerConfig.showApiBase && (
                                    <PageLabelWithValue>
                                        <PageLabel required={providerConfig.apiBaseRequired}>API Base URL</PageLabel>
                                        <Input
                                            {...register("apiBase", {
                                                required: providerConfig.apiBaseRequired ? "API Base URL is required" : false,
                                            })}
                                            aria-invalid={!!errors.apiBase}
                                        />
                                        {errors.apiBase && <ErrorLabel>{getErrorMessage(errors.apiBase)}</ErrorLabel>}
                                    </PageLabelWithValue>
                                )}

                                {/* Provider-specific fields */}
                                {providerConfig.fields.length > 0 && <>{providerConfig.fields.map((field: ProviderField) => renderField(field))}</>}

                                {/* Authentication Type - Show only provider's allowed auth types */}
                                <div>
                                    <PageLabel required>Authentication Type</PageLabel>
                                    <Controller
                                        name="authType"
                                        control={control}
                                        rules={{ required: "Authentication type is required" }}
                                        render={({ field }) => (
                                            <div className="mt-2 flex gap-4">
                                                {providerConfig?.allowedAuthTypes.map(authType => (
                                                    <label key={authType} className="flex cursor-pointer items-center gap-2">
                                                        <input
                                                            type="radio"
                                                            value={authType}
                                                            checked={field.value === authType}
                                                            onChange={() => {
                                                                console.log("[ModelEdit] Auth type changed to:", authType);
                                                                field.onChange(authType);
                                                            }}
                                                        />
                                                        <span className="text-sm">{authTypeLabels[authType as AuthType]}</span>
                                                    </label>
                                                ))}
                                            </div>
                                        )}
                                    />
                                    {errors.authType && <ErrorLabel>{getErrorMessage(errors.authType)}</ErrorLabel>}
                                </div>

                                {/* Render auth credential fields based on selected auth type */}
                                {selectedAuthType && AUTH_FIELDS[selectedAuthType as AuthType] && <>{AUTH_FIELDS[selectedAuthType as AuthType].map((field: ProviderField) => renderField(field))}</>}

                                {/* Model Name - Shown after authentication is configured */}
                                <PageLabelWithValue>
                                    <PageLabel required>Model Name</PageLabel>
                                    <Controller
                                        name="modelName"
                                        control={control}
                                        rules={{ required: "Model name is required" }}
                                        render={({ field }) => {
                                            // Use dynamic models if available, otherwise use cached models from modelsByProvider
                                            const cachedModels = modelsByProvider[selectedProvider] || [];
                                            const modelItems = dynamicModels.length > 0 ? dynamicModels : cachedModels;
                                            return (
                                                <DropDown
                                                    value={field.value}
                                                    onValueChange={field.onChange}
                                                    items={modelItems.map((model: { id: string; label: string }) => ({
                                                        id: model.id,
                                                        label: model.id, // Display model ID in input field
                                                    }))}
                                                    placeholder="Select a model..."
                                                    invalid={!!errors.modelName}
                                                    onOpen={handleModelDropdownOpen}
                                                />
                                            );
                                        }}
                                    />
                                    {errors.modelName && <ErrorLabel>{getErrorMessage(errors.modelName)}</ErrorLabel>}
                                </PageLabelWithValue>

                                {/* Advanced Parameters Section - Collapsible */}
                                <details className="group border-t pt-4">
                                    <summary className="text-foreground hover:text-secondary-foreground cursor-pointer text-sm font-medium select-none">Advanced Settings</summary>
                                    <div className="mt-4 flex flex-col gap-6">
                                        {/* Common Parameters - Temperature and Max Tokens */}
                                        {!providerConfig.hideCommonParams && COMMON_MODEL_PARAMS.length > 0 && <>{COMMON_MODEL_PARAMS.map((field: ProviderField) => renderField(field))}</>}

                                        {/* Custom Parameters */}
                                        <div className="border-t pt-4">
                                            <div className="flex items-start justify-between">
                                                <div>
                                                    <PageLabel>Custom Parameters</PageLabel>
                                                    <p className="text-secondary-foreground mt-1 text-sm">Add any additional parameters supported by your model provider.</p>
                                                </div>
                                                <Button type="button" variant="ghost" size="sm" onClick={handleAddCustomParam}>
                                                    <Plus className="mr-2 size-4" />
                                                    New Pair
                                                </Button>
                                            </div>
                                            <div className="mt-4">
                                                <Controller
                                                    name="customParams"
                                                    control={control}
                                                    rules={{
                                                        validate: params => {
                                                            if (!params || params.length === 0) return true;
                                                            for (const param of params) {
                                                                if (!param.key || !param.key.trim()) {
                                                                    return "Custom parameter keys cannot be empty";
                                                                }
                                                                if (!param.value || !param.value.trim()) {
                                                                    return "Custom parameter values cannot be empty";
                                                                }
                                                            }
                                                            return true;
                                                        },
                                                    }}
                                                    render={() => <KeyValuePairList name="customParams" error={errors.customParams} minPairs={0} />}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </details>
                            </>
                        )}
                    </PageSection>
                </form>
            </div>
        </FormProvider>
    );
};
