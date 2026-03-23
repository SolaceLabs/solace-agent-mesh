import { useEffect, useState, useCallback, useRef } from "react";
import { useForm, FormProvider, Controller } from "react-hook-form";
import { Input, Textarea, Button } from "@/lib/components/ui";
import { Plus } from "lucide-react";

import type { ModelConfig } from "@/lib/api/models";
import { PageSection, PageLabel } from "../common/PageCommon";
import { PasswordInput, FormField, TextInput } from "../common/FormComponents";
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
    const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
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

        // Password fields use the dedicated PasswordInput component
        if (field.type === "password") {
            return (
                <PasswordInput
                    key={field.name}
                    name={field.name}
                    label={field.label}
                    register={register}
                    error={errors[field.name] as { message?: string }}
                    helpText={field.helpText}
                    required={isRequiredField}
                    placeholder={field.placeholder}
                    showPassword={showPassword[field.name] || false}
                    onToggle={() => setShowPassword(prev => ({ ...prev, [field.name]: !prev[field.name] }))}
                />
            );
        }

        // Textarea fields use FormField wrapper
        if (field.type === "textarea") {
            return (
                <FormField key={field.name} label={field.label} required={isRequiredField} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
                    <Textarea
                        rows={6}
                        placeholder={field.placeholder}
                        {...register(field.name, {
                            required: isRequiredField ? `${field.label} is required` : false,
                        })}
                        aria-invalid={!!errors[field.name]}
                    />
                </FormField>
            );
        }

        // Text and number fields use TextInput component
        return (
            <TextInput
                key={field.name}
                name={field.name}
                label={field.label}
                register={register}
                error={errors[field.name] as { message?: string }}
                helpText={field.helpText}
                required={isRequiredField}
                type={field.type === "number" ? "number" : "text"}
                inputMode={field.type === "number" ? "decimal" : undefined}
                step={field.type === "number" ? field.step : undefined}
                min={field.type === "number" ? field.min : undefined}
                max={field.type === "number" ? field.max : undefined}
            />
        );
    };

    const onFormSubmit = async (data: FormData) => {
        await onSave(data);
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
                <form id="model-form" className="w-full max-w-[1200px]" onSubmit={handleSubmit(onFormSubmit)}>
                    <PageSection className="gap-6">
                        {/* Display Name / Alias - Always Visible */}
                        <FormField
                            label="Display Name"
                            required
                            error={errors.alias as { message?: string }}
                            helpText="Provide a short, descriptive name for this model for others in your organization to reference. Example: 'Analysis'."
                            statusIndicator={!isNew && modelToEdit?.alias.toLowerCase() === "general" ? <div className="text-xs text-orange-600">Cannot be changed</div> : undefined}
                        >
                            <Input
                                {...register("alias", { required: "Display name is required" })}
                                aria-invalid={!!errors.alias}
                                disabled={!isNew && modelToEdit?.alias.toLowerCase() === "general"}
                                title={!isNew && modelToEdit?.alias.toLowerCase() === "general" ? "The General model's name cannot be changed" : ""}
                            />
                        </FormField>

                        {/* Description - Always Visible */}
                        <FormField label="Description" required error={errors.description as { message?: string }} helpText="Describe types of tasks this model is suitable or not suitable for.">
                            <Textarea {...register("description", { required: "Description is required" })} rows={4} maxLength={1001} aria-invalid={!!errors.description} />
                        </FormField>

                        {/* Provider Dropdown - Always Visible */}
                        <FormField label="Model Provider" required error={errors.provider as { message?: string }}>
                            <Controller
                                name="provider"
                                control={control}
                                rules={{ required: "Provider is required" }}
                                render={({ field }) => <ProviderSelect value={field.value} onValueChange={field.onChange} providers={providers} invalid={!!errors.provider} />}
                            />
                        </FormField>

                        {/* Provider-specific fields only shown after provider selection */}
                        {selectedProvider && providerConfig && (
                            <>
                                {/* API Base (conditional) */}
                                {providerConfig.showApiBase && (
                                    <FormField label="API Base URL" required={providerConfig.apiBaseRequired} error={errors.apiBase as { message?: string }}>
                                        <Input
                                            {...register("apiBase", {
                                                required: providerConfig.apiBaseRequired ? "API Base URL is required" : false,
                                            })}
                                            aria-invalid={!!errors.apiBase}
                                        />
                                    </FormField>
                                )}

                                {/* Provider-specific fields */}
                                {providerConfig.fields.length > 0 && <>{providerConfig.fields.map((field: ProviderField) => renderField(field))}</>}

                                {/* Authentication Type - Only show if provider has multiple auth types */}
                                {providerConfig?.allowedAuthTypes && providerConfig.allowedAuthTypes.length > 1 && (
                                    <FormField label="Authentication Type" required error={errors.authType as { message?: string }}>
                                        <Controller
                                            name="authType"
                                            control={control}
                                            rules={{ required: "Authentication type is required" }}
                                            render={({ field }) => (
                                                <div className="flex gap-4">
                                                    {providerConfig.allowedAuthTypes.map(authType => (
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
                                    </FormField>
                                )}

                                {/* Render auth credential fields based on selected auth type */}
                                {selectedAuthType && AUTH_FIELDS[selectedAuthType as AuthType] && <>{AUTH_FIELDS[selectedAuthType as AuthType].map((field: ProviderField) => renderField(field))}</>}

                                {/* Model Name - Shown after authentication is configured */}
                                <FormField label="Model Name" required error={errors.modelName as { message?: string }}>
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
                                </FormField>

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
