/**
 * Model provider configuration and utilities.
 * Uses LiteLLM provider specifications to define required fields per provider.
 */

// ============================================================================
// Redacted credentials placeholder and field names
// ============================================================================

/**
 * Placeholder value for redacted credential fields when editing
 * Shows user that a credential exists without exposing it
 * Should be stripped out before submitting to server
 */
export const REDACTED_CREDENTIAL_PLACEHOLDER = "<encrypted>";

/**
 * Mapping of backend authConfig keys to form field names for sensitive credentials
 * Used for populating form fields when editing with redacted values
 */
export const AUTH_CONFIG_TO_FORM_FIELD_MAP: Record<string, string> = {
    api_key: "apiKey",
    client_id: "clientId",
    client_secret: "clientSecret",
    aws_access_key_id: "awsAccessKeyId",
    aws_secret_access_key: "awsSecretAccessKey",
    aws_session_token: "awsSessionToken",
    gcp_service_account_json: "gcpServiceAccountJson",
};

/**
 * Form field names that contain sensitive credentials and are redacted by the server
 * Used for:
 * - Populating with REDACTED_CREDENTIAL_PLACEHOLDER during edit
 * - Stripping placeholder values before submission
 */
export const REDACTED_CREDENTIAL_FIELDS = Object.values(AUTH_CONFIG_TO_FORM_FIELD_MAP);

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

export interface ProviderConfig {
    id: string;
    label: string;
    showApiBase: boolean;
    apiBaseRequired?: boolean;
    apiBasePlaceholder?: string;
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
        required: true,
        storageTarget: "model_params",
    },
];

const VERTEX_AI_FIELDS: ProviderField[] = [
    {
        name: "vertexProject",
        label: "GCP Project ID",
        type: "text",
        required: true,
        storageTarget: "model_params",
    },
    {
        name: "vertexLocation",
        label: "GCP Region",
        type: "text",
        required: true,
        storageTarget: "model_params",
    },
];

const BEDROCK_FIELDS: ProviderField[] = [
    {
        name: "awsRegionName",
        label: "AWS Region",
        type: "text",
        required: true,
        storageTarget: "model_params",
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
            name: "oauthTokenRefreshBufferSeconds",
            label: "Token Refresh Buffer (seconds)",
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
    ],
    gcp_service_account: [
        {
            name: "gcpServiceAccountJson",
            label: "Service Account JSON",
            type: "textarea",
            required: true,
            helpText: "Paste the full JSON key file contents",
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
        helpText: "Controls randomness (0-2)",
        storageTarget: "model_params",
        min: 0,
        max: 2,
        step: 0.1,
    },
    {
        name: "maxTokens",
        label: "Max Tokens",
        type: "number",
        required: false,
        helpText: "Maximum number of tokens in response",
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
        apiBasePlaceholder: "https://<your-resource>.openai.azure.com/",
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
        fields: VERTEX_AI_FIELDS,
        modelNamePlaceholder: "vertex_ai/gemini-1.5-pro",
        allowedAuthTypes: ["gcp_service_account"],
    },
    bedrock: {
        id: "bedrock",
        label: "Amazon Bedrock",
        showApiBase: false,
        fields: BEDROCK_FIELDS,
        modelNamePlaceholder: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        allowedAuthTypes: ["aws_iam"],
    },
    ollama: {
        id: "ollama",
        label: "Ollama",
        showApiBase: true,
        apiBaseRequired: true,
        apiBasePlaceholder: "http://localhost:11434",
        fields: [],
        modelNamePlaceholder: "ollama/llama2",
        allowedAuthTypes: ["apikey", "none"],
    },
    custom: {
        id: "custom",
        label: "Custom",
        description: "Configure a provider that implements the OpenAI-compatible API protocol",
        showApiBase: true,
        apiBaseRequired: false,
        apiBasePlaceholder: "https://api.example.com",
        fields: [],
        modelNamePlaceholder: "my-model-id",
        allowedAuthTypes: ["apikey", "oauth2", "none"],
    },
};

/**
 * Get the configuration for a specific provider.
 * Returns the provider config with field definitions, auth types, and placeholders.
 */
export function getProviderConfig(providerId: string): ProviderConfig {
    return PROVIDER_CONFIGS[providerId] || PROVIDER_CONFIGS.custom;
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
 */
export function buildModelPayload(data: ModelFormData) {
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
