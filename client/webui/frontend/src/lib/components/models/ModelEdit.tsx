import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useForm, FormProvider, Controller } from "react-hook-form";
import { Input, Textarea, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { Plus } from "lucide-react";
import { TestConnectionSection } from "./TestConnectionSection";

import type { ModelConfig } from "@/lib/api/models";
import { useSupportedModels, type SupportedModelsQueryParams } from "@/lib/api/models";
import { PageSection, PageLabel, FormFieldLayoutItem } from "../common/PageCommon";
import { PasswordInput } from "@/lib/components/common";
import { getProviderConfig, buildModelPayload, AUTH_FIELDS, AUTH_TYPE_LABELS, COMMON_MODEL_PARAMS, AUTH_CONFIG_TO_FORM_FIELD_MAP, type AuthType, type ProviderField, type ModelProvider, type ModelFormData } from "./modelProviderUtils";
import { fetchSupportedParams } from "@/lib/api/models/service";
import { ProviderSelect } from "./ProviderSelect";
import { ComboBox } from "@/lib/components/ui";
import { KeyValuePairList } from "../common/KeyValuePairList";
import { DEFAULT_MODEL_ALIASES } from "./common";
import { useDebounce } from "@/lib/hooks";

interface ModelEditProps {
    isNew: boolean;
    modelToEdit: ModelConfig | null;
    onSave: (data: ModelFormData, dirtyFields: Partial<Record<string, boolean>>) => Promise<void>;
    onValidityChange: (isValid: boolean) => void;
    onDirtyStateChange?: (isDirty: boolean) => void;
    modelsByProvider?: Record<string, Array<{ id: string; label: string }>>;
    availableProviders?: ModelProvider[];
    onProviderChange?: (provider: string) => Promise<void>;
}

export const ModelEdit = ({ isNew, modelToEdit, onSave, onValidityChange, onDirtyStateChange, modelsByProvider = {}, availableProviders = [], onProviderChange }: ModelEditProps) => {
    const methods = useForm<ModelFormData>({
        mode: "onSubmit",
        reValidateMode: "onChange",
        defaultValues: {
            customParams: [],
            cache_strategy: "5m",
        },
    });

    const [providerConfig, setProviderConfig] = useState<ReturnType<typeof getProviderConfig> | null>(null);
    const [storedCredentialFields, setStoredCredentialFields] = useState<Set<string>>(new Set());
    const [queryParams, setQueryParams] = useState<SupportedModelsQueryParams | null>(null);
    const { data: dynamicModels = [], isLoading: isLoadingModels, isError: hasFetchError } = useSupportedModels(queryParams);
    const [supportedParams, setSupportedParams] = useState<string[] | null>(null);
    const hasInitializedFromModelRef = useRef(false);
    const {
        register,
        control,
        formState: { errors, isDirty, isValid, dirtyFields },
        handleSubmit,
        watch,
        setValue,
        reset,
        getValues,
    } = methods;

    const handleAddCustomParam = useCallback(() => {
        const currentParams = getValues("customParams") ?? [];
        setValue("customParams", [{ key: "", value: "" }, ...currentParams]);
    }, [getValues, setValue]);

    const customParams = watch("customParams") ?? [];
    // Serialize customParams for useMemo deps — watch() returns a mutated array
    // (same reference), so shallow comparison alone won't detect content changes.
    const customParamsJson = JSON.stringify(customParams);
    const hasEmptyCustomParam = useMemo(() => customParams.some((p: { key: string; value: string }) => !p.key?.trim() || !p.value?.trim()), [customParamsJson]);
    const unsupportedCustomKeys = useMemo(() => {
        if (!supportedParams || supportedParams.length === 0) return [];
        return customParams.filter((p: { key: string }) => p.key && !supportedParams.includes(p.key)).map((p: { key: string }) => p.key);
    }, [customParamsJson, supportedParams]);

    const selectedProvider = watch("provider");
    const selectedAuthType = watch("authType");
    const apiBase = watch("apiBase");
    const apiKey = watch("apiKey");
    const selectedModelName = watch("modelName");
    const debouncedModelName = useDebounce(selectedModelName, 500);
    // Watch all credential fields so isAuthCredentialsConfigured re-evaluates on change.
    // Values aren't used directly — isConfigured() reads via getValues() — but the
    // watch() subscription is needed to trigger a re-render when any field changes.
    watch(["clientId", "clientSecret", "tokenUrl", "awsAccessKeyId", "awsSecretAccessKey", "awsRegionName", "vertexCredentials", "vertexProject", "vertexLocation"]);

    // Determine if we have sufficient provider and auth config to enable model dropdown
    // For editing: just need provider + auth type (cached models already available)
    // For creating: need provider + auth type + credentials filled in (must fetch models dynamically)
    const isProviderConfigured = !!selectedProvider && !!selectedAuthType;

    const isAuthCredentialsConfigured = (() => {
        if (!selectedAuthType) return false;
        if (selectedAuthType === "none") return true;

        // When editing, stored credentials count as "configured"
        const isConfigured = (fieldName: string) => {
            return !!getValues(fieldName) || storedCredentialFields.has(fieldName);
        };

        if (selectedAuthType === "apikey") return isConfigured("apiKey");
        if (selectedAuthType === "oauth2") {
            return isConfigured("clientId") && isConfigured("clientSecret") && !!getValues("tokenUrl");
        }
        if (selectedAuthType === "aws_iam") {
            return isConfigured("awsAccessKeyId") && isConfigured("awsSecretAccessKey");
        }
        if (selectedAuthType === "gcp_service_account") {
            return isConfigured("vertexCredentials");
        }
        return false;
    })();

    // For editing: enable if provider and auth type are set (cached models available)
    // For creating: also need credentials to be filled in (to fetch models)
    // Additionally, if the provider requires an API base URL, it must be filled in
    const isApiBaseReady = !providerConfig?.apiBaseRequired || !!apiBase;
    const isModelDropdownEnabled = isProviderConfigured && isApiBaseReady && (!isNew || isAuthCredentialsConfigured);

    useEffect(() => {
        onDirtyStateChange?.(isDirty);
    }, [isDirty, onDirtyStateChange]);

    useEffect(() => {
        onValidityChange(isValid);
    }, [isValid, onValidityChange]);

    // Update provider config and reset dynamic fields when provider changes
    useEffect(() => {
        if (selectedProvider) {
            const config = getProviderConfig(selectedProvider);
            setProviderConfig(config);
            setQueryParams(null); // Reset query so next dropdown open fetches fresh
            setSupportedParams(null); // Reset supported params when provider changes

            // Skip resetting fields on initial model load; only reset when user manually changes provider
            if (hasInitializedFromModelRef.current && !isNew && modelToEdit && modelToEdit.provider === selectedProvider) {
                hasInitializedFromModelRef.current = false; // Clear flag so future changes will reset
                // Still fetch models for the provider
                onProviderChange?.(selectedProvider);
                return;
            }

            setStoredCredentialFields(new Set()); // Clear stored credential indicators from previous provider

            // Fetch models for this provider if callback provided
            onProviderChange?.(selectedProvider);

            // Reset all fields except alias, description, and custom params —
            // start fresh for the new provider while preserving user intent
            reset({
                alias: getValues("alias"),
                description: getValues("description"),
                provider: selectedProvider,
                authType: config.allowedAuthTypes[0],
                customParams: getValues("customParams") ?? [],
                cache_strategy: "5m",
            });
        }
        // Omitting reset, getValues, onProviderChange — these are stable refs from useForm/props
        // and including them would cause unnecessary re-runs of the provider reset logic
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedProvider, isNew, modelToEdit]);

    // Fetch supported params when provider or model name changes (debounced to avoid
    // excessive requests while the user types a custom model name in the ComboBox)
    useEffect(() => {
        if (!selectedProvider || !debouncedModelName) {
            setSupportedParams(null);
            return;
        }
        let cancelled = false;
        fetchSupportedParams(selectedProvider, debouncedModelName)
            .then(params => {
                if (!cancelled) setSupportedParams(params);
            })
            .catch(() => {
                if (!cancelled) setSupportedParams(null);
            });
        return () => {
            cancelled = true;
        };
    }, [selectedProvider, debouncedModelName]);

    // Clear query params when credentials change so next dropdown open fetches fresh models
    useEffect(() => {
        if (selectedProvider) {
            setQueryParams(null);
        }
    }, [selectedAuthType, apiKey, apiBase, selectedProvider]);

    // When the model dropdown opens, commit the current form credentials as query params.
    // React Query handles caching: if params haven't changed since the last successful
    // fetch the cached result is returned; if they changed a fresh request is made.
    // In editing mode, modelId is passed so the server can merge stored credentials
    // with any overrides from the form (e.g., user changed API key but not secret).
    //
    // If the parent already supplied models for this provider (initial edit-mode fetch)
    // and credentials haven't been touched (queryParams is still null), skip the fetch
    // and let the ComboBox render from modelsByProvider directly.
    const handleModelDropdownOpen = useCallback(() => {
        if (!selectedProvider) return;

        if (queryParams === null && (modelsByProvider[selectedProvider]?.length ?? 0) > 0) {
            return;
        }

        const currentProviderConfig = providerConfig || getProviderConfig(selectedProvider);
        const modelParams: Record<string, unknown> = {};
        for (const field of currentProviderConfig.fields) {
            const val = getValues(field.name);
            if (val != null && val !== "") {
                modelParams[field.name] = val;
            }
        }

        const formData = getValues() as ModelFormData;
        const payload = buildModelPayload({
            ...formData,
            alias: formData.alias || "",
            modelName: formData.modelName || "",
        });

        setQueryParams({
            provider: selectedProvider,
            modelId: !isNew ? modelToEdit?.id : undefined,
            apiBase: apiBase || undefined,
            authConfig: payload.authConfig,
            modelParams: Object.keys(modelParams).length > 0 ? modelParams : undefined,
        });
    }, [selectedProvider, isNew, apiBase, modelToEdit, providerConfig, getValues, queryParams, modelsByProvider]);

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
            if (modelToEdit.provider === "custom" && modelName?.startsWith("openai/")) {
                modelName = modelName.substring(7);
            }

            setValue("modelName", modelName);
            setValue("apiBase", modelToEdit.apiBase || "");
            setValue("authType", modelToEdit.authType || "apikey");
            setValue("description", modelToEdit.description || "");

            // Track which credential fields have stored values on the server.
            // The backend redacts secrets (removes them from the response), so any key
            // present in authConfig with a truthy value is a non-redacted field (like tokenUrl).
            // Keys that are absent or have falsy values are redacted secrets — these are
            // the fields that have stored values server-side.
            if (modelToEdit.authConfig) {
                const stored = new Set<string>();
                Object.entries(AUTH_CONFIG_TO_FORM_FIELD_MAP).forEach(([configKey, fieldName]) => {
                    const value = modelToEdit.authConfig[configKey];
                    if (value) {
                        // Non-redacted field — populate with the actual value
                        setValue(fieldName, String(value));
                    } else {
                        // Redacted by server — mark as having a stored value
                        stored.add(fieldName);
                    }
                });
                setStoredCredentialFields(stored);
            }

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
                COMMON_MODEL_PARAMS.forEach((field: ProviderField) => {
                    knownParamNames.add(field.name);
                    if (field.name in modelToEdit.modelParams) {
                        setValue(field.name, String(modelToEdit.modelParams[field.name]));
                    }
                });

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
        const isAuthCredentialField = field.storageTarget === "auth" && ["apiKey", "clientSecret", "awsSecretAccessKey", "awsSessionToken", "vertexCredentials"].includes(field.name);
        const isRequiredField = field.required && (!isAuthCredentialField || isNew);

        // Password fields use the dedicated PasswordInput component
        if (field.type === "password") {
            return (
                <FormFieldLayoutItem key={field.name} label={field.label} required={field.required} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
                    <PasswordInput name={field.name} control={control} hasStoredValue={storedCredentialFields.has(field.name)} placeholder={field.placeholder} rules={{ required: isRequiredField ? `${field.label} is required` : false }} />
                </FormFieldLayoutItem>
            );
        }

        // Textarea fields use FormField wrapper
        if (field.type === "textarea") {
            return (
                <FormFieldLayoutItem key={field.name} label={field.label} required={field.required} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
                    <Textarea
                        rows={6}
                        placeholder={field.placeholder}
                        {...register(field.name, {
                            required: isRequiredField ? `${field.label} is required` : false,
                        })}
                        aria-invalid={!!errors[field.name]}
                    />
                </FormFieldLayoutItem>
            );
        }

        // Select fields use native Select component
        if (field.type === "select") {
            return (
                <FormFieldLayoutItem key={field.name} label={field.label} required={field.required} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
                    <Controller
                        name={field.name}
                        control={control}
                        rules={{ required: isRequiredField ? `${field.label} is required` : false }}
                        render={({ field: fieldProps }) => (
                            <Select value={String(fieldProps.value ?? "")} onValueChange={fieldProps.onChange}>
                                <SelectTrigger aria-invalid={!!errors[field.name]}>
                                    <SelectValue placeholder={`Select ${field.label.toLowerCase()}`} />
                                </SelectTrigger>
                                <SelectContent>
                                    {(field.options || []).map((option: { value: string; label: string }) => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    />
                </FormFieldLayoutItem>
            );
        }

        // Text and number fields use Input component
        const rules: Record<string, unknown> = {
            required: isRequiredField ? `${field.label} is required` : false,
        };
        if (field.type === "number") {
            if (field.min !== undefined) rules.min = { value: field.min, message: `Minimum value is ${field.min}` };
            if (field.max !== undefined) rules.max = { value: field.max, message: `Maximum value is ${field.max}` };
        }
        return (
            <FormFieldLayoutItem key={field.name} label={field.label} required={field.required} error={errors[field.name] as { message?: string }} helpText={field.helpText}>
                <Input
                    {...register(field.name, rules)}
                    type={field.type === "number" ? "number" : "text"}
                    inputMode={field.type === "number" ? "decimal" : undefined}
                    step={field.type === "number" ? field.step : undefined}
                    min={field.type === "number" ? field.min : undefined}
                    max={field.type === "number" ? field.max : undefined}
                    placeholder={field.placeholder}
                    aria-invalid={!!errors[field.name]}
                />
            </FormFieldLayoutItem>
        );
    };

    const onFormSubmit = async (data: ModelFormData) => {
        await onSave(data, dirtyFields);
    };

    const isDefaultModel = !isNew && modelToEdit ? DEFAULT_MODEL_ALIASES.includes(modelToEdit.alias.toLowerCase()) : false;

    return (
        <FormProvider {...methods}>
            <div>
                <form id="model-form" className="w-full max-w-[1200px]" onSubmit={handleSubmit(onFormSubmit)}>
                    <PageSection className="gap-6">
                        <FormFieldLayoutItem
                            label="Display Name"
                            required
                            error={errors.alias as { message?: string }}
                            helpText="Provide a short, descriptive name for this model for others in your organization to reference. Example: 'Analysis'."
                            statusIndicator={isDefaultModel ? <div className="text-xs text-(--warning-wMain)">Cannot be changed</div> : undefined}
                        >
                            <Input {...register("alias", { required: "Display name is required" })} aria-invalid={!!errors.alias} disabled={isDefaultModel} title={isDefaultModel ? "This model's name cannot be changed" : ""} />
                        </FormFieldLayoutItem>

                        {/* Description - Always Visible */}
                        <FormFieldLayoutItem label="Description" required error={errors.description as { message?: string }} helpText="Describe types of tasks this model is suitable or not suitable for.">
                            <Textarea {...register("description", { required: "Description is required" })} rows={4} maxLength={1001} aria-invalid={!!errors.description} />
                        </FormFieldLayoutItem>

                        {/* Provider Dropdown - Always Visible */}
                        <FormFieldLayoutItem label="Model Provider" required error={errors.provider as { message?: string }}>
                            <Controller
                                name="provider"
                                control={control}
                                rules={{ required: "Provider is required" }}
                                render={({ field }) => <ProviderSelect value={field.value} onValueChange={field.onChange} providers={providers} invalid={!!errors.provider} />}
                            />
                        </FormFieldLayoutItem>

                        {/* Provider-specific fields only shown after provider selection */}
                        {selectedProvider && providerConfig && (
                            <>
                                {/* API Base (conditional) */}
                                {providerConfig.showApiBase && (
                                    <FormFieldLayoutItem label="API Base URL" required={providerConfig.apiBaseRequired} error={errors.apiBase as { message?: string }}>
                                        <Input
                                            {...register("apiBase", {
                                                required: providerConfig.apiBaseRequired ? "API Base URL is required" : false,
                                            })}
                                            aria-invalid={!!errors.apiBase}
                                        />
                                    </FormFieldLayoutItem>
                                )}

                                {/* Provider-specific fields */}
                                {providerConfig.fields.length > 0 && <>{providerConfig.fields.map((field: ProviderField) => renderField(field))}</>}

                                {/* Authentication Type - Only show if provider has multiple auth types */}
                                {providerConfig?.allowedAuthTypes && providerConfig.allowedAuthTypes.length > 1 && (
                                    <FormFieldLayoutItem label="Authentication Type" required error={errors.authType as { message?: string }}>
                                        <Controller
                                            name="authType"
                                            control={control}
                                            rules={{ required: "Authentication type is required" }}
                                            render={({ field }) => (
                                                <div className="flex gap-4">
                                                    {providerConfig.allowedAuthTypes.map(authType => (
                                                        <label key={authType} className="flex cursor-pointer items-center gap-2">
                                                            <input type="radio" value={authType} checked={field.value === authType} onChange={() => field.onChange(authType)} />
                                                            <span className="text-sm">{AUTH_TYPE_LABELS[authType as AuthType]}</span>
                                                        </label>
                                                    ))}
                                                </div>
                                            )}
                                        />
                                    </FormFieldLayoutItem>
                                )}

                                {/* Render auth credential fields based on selected auth type */}
                                {selectedAuthType && AUTH_FIELDS[selectedAuthType as AuthType] && <>{AUTH_FIELDS[selectedAuthType as AuthType].map((field: ProviderField) => renderField(field))}</>}

                                {/* Model Name - Shown after authentication is configured */}
                                <FormFieldLayoutItem
                                    label="Model Name"
                                    required
                                    error={hasFetchError ? { message: "Unable to find models. Verify that your model connection details above are correct." } : (errors.modelName as { message?: string })}
                                    helpText={isLoadingModels ? "Finding your available models..." : !isModelDropdownEnabled ? "Configure provider and authentication to select a model" : undefined}
                                >
                                    <Controller
                                        name="modelName"
                                        control={control}
                                        rules={{ required: "Model name is required" }}
                                        render={({ field }) => {
                                            // Use dynamic models if available, otherwise use cached models from modelsByProvider
                                            const cachedModels = modelsByProvider[selectedProvider] || [];
                                            const modelItems = dynamicModels.length > 0 ? dynamicModels : cachedModels;

                                            let displayItems = modelItems.map((model: { id: string; label: string }) => ({
                                                id: model.id,
                                                label: model.id,
                                            }));

                                            // Always include the selected model in the list, even if it's not in the fetched models
                                            // This ensures the selected model shows up when we clear the list to force a refetch
                                            if (field.value && !displayItems.find(item => item.id === field.value)) {
                                                displayItems = [{ id: field.value, label: field.value }, ...displayItems];
                                            }

                                            return (
                                                <ComboBox
                                                    value={field.value}
                                                    onValueChange={field.onChange}
                                                    items={displayItems}
                                                    placeholder="Type or select a model..."
                                                    disabled={!isModelDropdownEnabled}
                                                    invalid={!!errors.modelName}
                                                    isLoading={isLoadingModels}
                                                    onOpen={handleModelDropdownOpen}
                                                    allowCustomValue
                                                />
                                            );
                                        }}
                                    />
                                </FormFieldLayoutItem>

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
                                                <Button type="button" variant="ghost" size="sm" onClick={handleAddCustomParam} disabled={hasEmptyCustomParam}>
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
                                                    render={() => (
                                                        <>
                                                            <KeyValuePairList name="customParams" error={errors.customParams} minPairs={0} emptyMessage="No custom parameters added yet" />
                                                            {unsupportedCustomKeys.length > 0 && (
                                                                <p className="mt-2 text-xs text-(--warning-wMain)">Some custom parameters may not be supported by the selected model: {unsupportedCustomKeys.join(", ")}</p>
                                                            )}
                                                        </>
                                                    )}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </details>

                                {/* Test Connection */}
                                <TestConnectionSection
                                    getFormData={() => getValues() as ModelFormData}
                                    getDirtyFields={() => dirtyFields}
                                    isNew={isNew}
                                    modelId={modelToEdit?.id}
                                    disabled={!selectedProvider || !selectedModelName || (isNew && !isAuthCredentialsConfigured)}
                                />
                            </>
                        )}
                    </PageSection>
                </form>
            </div>
        </FormProvider>
    );
};
