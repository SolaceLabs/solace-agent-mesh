/**
 * Model provider configuration and utilities.
 * Uses LiteLLM provider specifications to define required fields per provider.
 */

// ============================================================================
// Auth credential field mapping
// ============================================================================

/**
 * Mapping of backend authConfig keys to form field names for sensitive credentials.
 * Used to determine which form fields have stored values during edit,
 * and to check dirtyFields when building payloads.
 */
export const AUTH_CONFIG_TO_FORM_FIELD_MAP: Record<string, string> = {
    api_key: "apiKey",
    client_id: "clientId",
    client_secret: "clientSecret",
    aws_access_key_id: "awsAccessKeyId",
    aws_secret_access_key: "awsSecretAccessKey",
    aws_session_token: "awsSessionToken",
    vertex_credentials: "vertexCredentials",
    // Routing / connection fields (not secret, no placeholder redaction)
    audience: "oauthAudience",
    ca_cert: "oauthCaCert",
    max_retries: "oauthMaxRetries",
    aws_region_name: "awsRegionName",
    vertex_project: "vertexProject",
    vertex_location: "vertexLocation",
    api_version: "apiVersion",
};

export interface ModelProvider {
    id: string;
    label: string;
}

export type FieldType = "text" | "password" | "number" | "textarea" | "select";
export type AuthType = "apikey" | "oauth2" | "none" | "aws_iam" | "gcp_service_account";

export const AUTH_TYPE_LABELS: Record<AuthType, string> = {
    apikey: "API Key",
    oauth2: "OAuth2",
    none: "None",
    aws_iam: "AWS IAM",
    gcp_service_account: "GCP Service Account",
};

export interface ProviderField {
    name: string; // react-hook-form field key
    label: string;
    type: FieldType;
    required: boolean;
    placeholder?: string;
    helpText?: string;
    storageTarget: "model_params" | "auth";
    min?: number; // for number fields
    max?: number;
    step?: number;
    options?: Array<{ value: string; label: string }>; // for select fields
}

export interface SupportedModel {
    id: string;
    label: string;
}

/**
 * Flat form field values for the model edit form (react-hook-form shape).
 * Auth credential fields and model params are mapped to nested API structures
 * (authConfig, modelParams) during form submission in ModelEditPage.
 */
export interface ModelFormData {
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
    oauthAudience?: string;
    oauthCaCert?: string;
    oauthTokenRefreshBufferSeconds?: string;
    oauthMaxRetries?: string;
    awsAccessKeyId?: string;
    awsSecretAccessKey?: string;
    awsSessionToken?: string;
    awsRegionName?: string;
    vertexCredentials?: string;
    vertexProject?: string;
    vertexLocation?: string;
    customParams?: Array<{ key: string; value: string }>;
    maxInputTokens?: string;
    [key: string]: unknown;
}

export interface ProviderConfig {
    id: string;
    label: string;
    showApiBase: boolean;
    apiBaseRequired?: boolean;
    description?: string; // optional description of the provider
    fields: ProviderField[]; // provider-specific required/optional fields
    modelNamePlaceholder: string; // example shown in model name input
    hideCommonParams?: boolean; // if true, hide temperature/max_tokens (e.g., for custom provider)
    allowedAuthTypes: AuthType[]; // which auth types this provider supports
}

// ============================================================================
// Provider-specific field definitions (beyond common fields: alias, description, provider, modelName)
// ============================================================================

const AZURE_OPENAI_FIELDS: ProviderField[] = [
    {
        name: "apiVersion",
        label: "API Version",
        type: "text",
        required: false,
        storageTarget: "auth",
    },
];

// ============================================================================
// Authentication field definitions per auth type
// ============================================================================

export const AUTH_FIELDS: Record<AuthType, ProviderField[]> = {
    apikey: [
        {
            name: "apiKey",
            label: "API Key",
            type: "password",
            required: true,
            storageTarget: "auth",
        },
    ],
    oauth2: [
        {
            name: "tokenUrl",
            label: "Token URL",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "clientId",
            label: "Client ID",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "clientSecret",
            label: "Client Secret",
            type: "password",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "oauthScope",
            label: "OAuth Scope",
            type: "text",
            required: false,
            storageTarget: "auth",
        },
        {
            name: "oauthAudience",
            label: "OAuth Audience",
            type: "text",
            required: false,
            storageTarget: "auth",
        },
        {
            name: "oauthCaCert",
            label: "CA Certificate Path",
            type: "text",
            required: false,
            storageTarget: "auth",
        },
        {
            name: "oauthTokenRefreshBufferSeconds",
            label: "Token Refresh Buffer (seconds)",
            type: "number",
            required: false,
            storageTarget: "auth",
            min: 0,
        },
        {
            name: "oauthMaxRetries",
            label: "Max Retries",
            type: "number",
            required: false,
            storageTarget: "auth",
            min: 0,
        },
    ],
    none: [],
    aws_iam: [
        {
            name: "awsAccessKeyId",
            label: "AWS Access Key ID",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "awsSecretAccessKey",
            label: "AWS Secret Access Key",
            type: "password",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "awsSessionToken",
            label: "AWS Session Token",
            type: "password",
            required: false,
            storageTarget: "auth",
        },
        {
            name: "awsRegionName",
            label: "AWS Region",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
    ],
    gcp_service_account: [
        {
            name: "vertexCredentials",
            label: "Service Account JSON",
            type: "textarea",
            required: true,
            helpText: "Paste the full JSON key file contents",
            storageTarget: "auth",
        },
        {
            name: "vertexProject",
            label: "GCP Project ID",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
        {
            name: "vertexLocation",
            label: "GCP Region",
            type: "text",
            required: true,
            storageTarget: "auth",
        },
    ],
};

// ============================================================================
// Common model parameters (shown for all providers)
// ============================================================================

export const COMMON_MODEL_PARAMS: ProviderField[] = [
    {
        name: "temperature",
        label: "Temperature",
        type: "number",
        required: false,
        helpText: "Controls output randomness. Higher values produce more creative responses, lower values are more focused. Refer to your provider's documentation for the supported range.",
        storageTarget: "model_params",
        min: 0,
        max: 2,
        step: 0.1,
    },
    {
        name: "max_tokens",
        label: "Max Tokens",
        type: "number",
        required: false,
        helpText: "The maximum number of tokens to generate in the response. Sets an upper limit on output length.",
        storageTarget: "model_params",
        min: 1,
    },
    {
        name: "cache_strategy",
        label: "Prompt Caching Strategy",
        type: "select",
        required: false,
        helpText: "Controls how the model caches prompts for cost optimization",
        storageTarget: "model_params",
        options: [
            { value: "5m", label: "5 minutes (default)" },
            { value: "1h", label: "1 hour" },
            { value: "none", label: "Disabled" },
        ],
    },
];

// ============================================================================
// Provider configurations (LiteLLM-based)
// ============================================================================

const PROVIDER_CONFIGS: Record<string, ProviderConfig> = {
    openai: {
        id: "openai",
        label: "OpenAI",
        showApiBase: false,
        fields: [],
        modelNamePlaceholder: "gpt-4o-mini",
        allowedAuthTypes: ["apikey"],
    },
    anthropic: {
        id: "anthropic",
        label: "Anthropic",
        showApiBase: false,
        fields: [],
        modelNamePlaceholder: "claude-3-5-sonnet-20241022",
        allowedAuthTypes: ["apikey"],
    },
    azure_openai: {
        id: "azure_openai",
        label: "Azure OpenAI",
        showApiBase: true,
        apiBaseRequired: true,
        fields: AZURE_OPENAI_FIELDS,
        modelNamePlaceholder: "azure/<deployment-name>",
        allowedAuthTypes: ["apikey", "oauth2"],
    },
    google_ai_studio: {
        id: "google_ai_studio",
        label: "Google AI Studio",
        showApiBase: false,
        fields: [],
        modelNamePlaceholder: "gemini/gemini-1.5-pro",
        allowedAuthTypes: ["apikey"],
    },
    vertex_ai: {
        id: "vertex_ai",
        label: "Google Vertex AI",
        showApiBase: false,
        fields: [],
        modelNamePlaceholder: "vertex_ai/gemini-1.5-pro",
        allowedAuthTypes: ["gcp_service_account"],
    },
    bedrock: {
        id: "bedrock",
        label: "Amazon Bedrock",
        showApiBase: false,
        fields: [],
        modelNamePlaceholder: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        allowedAuthTypes: ["aws_iam"],
    },
    ollama: {
        id: "ollama",
        label: "Ollama",
        showApiBase: true,
        apiBaseRequired: true,
        fields: [],
        modelNamePlaceholder: "ollama/llama2",
        allowedAuthTypes: ["apikey", "none"],
    },
    custom: {
        id: "custom",
        label: "Custom",
        description: "Configure a provider that implements the OpenAI-compatible API protocol",
        showApiBase: true,
        apiBaseRequired: true,
        fields: [],
        modelNamePlaceholder: "my-model-id",
        allowedAuthTypes: ["apikey", "oauth2", "none"],
    },
};

/**
 * Get the configuration for a specific provider.
 * Returns the provider config with field definitions, auth types, and placeholders.
 */
export function getProviderConfig(providerId: string | null | undefined): ProviderConfig {
    return (providerId && PROVIDER_CONFIGS[providerId]) || PROVIDER_CONFIGS.custom;
}

/**
 * Display name lookup derived from PROVIDER_CONFIGS.
 * Single source of truth for provider labels across the UI.
 */
export const PROVIDER_DISPLAY_NAMES: Record<string, string> = Object.fromEntries(Object.values(PROVIDER_CONFIGS).map(c => [c.id, c.label]));

/**
 * All available providers sorted alphabetically with "custom" last.
 */
export const ALL_PROVIDERS: ModelProvider[] = Object.values(PROVIDER_CONFIGS)
    .map(({ id, label }) => ({ id, label }))
    .sort((a, b) => {
        if (a.id === "custom") return 1;
        if (b.id === "custom") return -1;
        return a.label.localeCompare(b.label);
    });

/**
 * Build model params and auth config from form data.
 * Shared between save and test connection flows.
 *
 * When dirtyFields is provided, credential fields are only included in authConfig
 * if the user actually modified them (based on react-hook-form's dirtyFields).
 * This prevents sending empty strings for unchanged credentials.
 */
export function buildModelPayload(data: ModelFormData, dirtyFields?: Partial<Record<string, boolean>>) {
    const providerConfig = getProviderConfig(data.provider);

    // Collect provider-specific fields, respecting storage target
    const modelParams: Record<string, unknown> = {};
    const providerAuthFields: Record<string, unknown> = {};
    for (const field of providerConfig.fields) {
        if (data[field.name] != null && data[field.name] !== "") {
            const value = field.type === "number" ? Number(data[field.name]) : data[field.name];
            if (field.storageTarget === "auth") {
                // Convert camelCase to snake_case to match auth_config key convention
                const snakeKey = field.name.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
                providerAuthFields[snakeKey] = value;
            } else {
                modelParams[field.name] = value;
            }
        }
    }

    // Add common model params (iterate over COMMON_MODEL_PARAMS for consistency)
    for (const field of COMMON_MODEL_PARAMS) {
        const value = data[field.name];
        if (value != null && value !== "") {
            modelParams[field.name] = field.type === "number" ? Number(value) : value;
        }
    }

    // Add custom parameters
    if (data.customParams && Array.isArray(data.customParams)) {
        data.customParams.forEach((param: { key: string; value: string }) => {
            if (param.key.trim()) {
                modelParams[param.key] = param.value;
            }
        });
    }

    // Helper: check if a credential field should be included in the payload.
    // If dirtyFields is provided, only include fields the user actually modified.
    // If dirtyFields is not provided (e.g., creating a new model), include all non-empty fields.
    const shouldIncludeCredential = (fieldName: string, value: unknown): boolean => {
        if (dirtyFields) {
            return !!dirtyFields[fieldName];
        }
        return !!value;
    };

    // Build auth config
    let authConfig: Record<string, unknown> = {};
    if (data.authType === "apikey") {
        authConfig = { type: "apikey" };
        if (shouldIncludeCredential("apiKey", data.apiKey)) {
            authConfig.api_key = data.apiKey;
        }
    } else if (data.authType === "oauth2") {
        authConfig = { type: "oauth2" };
        if (shouldIncludeCredential("clientId", data.clientId)) {
            authConfig.client_id = data.clientId;
        }
        if (shouldIncludeCredential("clientSecret", data.clientSecret)) {
            authConfig.client_secret = data.clientSecret;
        }
        if (data.tokenUrl) {
            authConfig.token_url = data.tokenUrl;
        }
        if (data.oauthScope) {
            authConfig.scope = data.oauthScope;
        }
        if (data.oauthAudience) {
            authConfig.audience = data.oauthAudience;
        }
        if (data.oauthCaCert) {
            authConfig.ca_cert = data.oauthCaCert;
        }
        if (data.oauthTokenRefreshBufferSeconds) {
            authConfig.token_refresh_buffer_seconds = Number(data.oauthTokenRefreshBufferSeconds);
        }
        if (data.oauthMaxRetries) {
            authConfig.max_retries = Number(data.oauthMaxRetries);
        }
    } else if (data.authType === "aws_iam") {
        authConfig = { type: "aws_iam" };
        if (shouldIncludeCredential("awsAccessKeyId", data.awsAccessKeyId)) {
            authConfig.aws_access_key_id = data.awsAccessKeyId;
        }
        if (shouldIncludeCredential("awsSecretAccessKey", data.awsSecretAccessKey)) {
            authConfig.aws_secret_access_key = data.awsSecretAccessKey;
        }
        if (shouldIncludeCredential("awsSessionToken", data.awsSessionToken)) {
            authConfig.aws_session_token = data.awsSessionToken;
        }
        if (data.awsRegionName) {
            authConfig.aws_region_name = data.awsRegionName;
        }
    } else if (data.authType === "gcp_service_account") {
        authConfig = { type: "gcp_service_account" };
        if (shouldIncludeCredential("vertexCredentials", data.vertexCredentials)) {
            authConfig.vertex_credentials = data.vertexCredentials;
        }
        if (data.vertexProject) {
            authConfig.vertex_project = data.vertexProject;
        }
        if (data.vertexLocation) {
            authConfig.vertex_location = data.vertexLocation;
        }
    } else {
        authConfig = { type: "none" };
    }

    // Merge provider-specific connection params (storageTarget: "auth") into authConfig
    Object.assign(authConfig, providerAuthFields);

    // Format model name with provider prefix if needed
    let modelName = data.modelName;
    if (!modelName.includes("/") && data.provider === "custom") {
        modelName = `openai/${modelName}`;
    }

    const maxInputTokensRaw = data.maxInputTokens;
    const maxInputTokensNum = maxInputTokensRaw != null && maxInputTokensRaw !== "" ? Number(maxInputTokensRaw) : null;
    const maxInputTokens = maxInputTokensNum != null && Number.isFinite(maxInputTokensNum) && maxInputTokensNum >= 1 ? Math.floor(maxInputTokensNum) : null;

    return {
        alias: data.alias.trim(),
        provider: data.provider,
        modelName,
        apiBase: data.apiBase || "",
        description: data.description || null,
        authType: data.authType,
        authConfig,
        modelParams,
        maxInputTokens,
    };
}

/**
 * Build the payload for testing a model connection.
 * Extracts only the fields needed by the test endpoint from a save payload.
 */
export function buildTestPayload(savePayload: ReturnType<typeof buildModelPayload>, modelId?: string) {
    return {
        provider: savePayload.provider,
        modelName: savePayload.modelName,
        apiBase: savePayload.apiBase || undefined,
        authConfig: savePayload.authConfig,
        modelParams: savePayload.modelParams,
        ...(modelId ? { modelId } : {}),
    };
}
