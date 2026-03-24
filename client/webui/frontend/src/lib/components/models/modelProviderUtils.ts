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

interface ModelResponseItem {
    id?: string;
    name?: string;
}

export type FieldType = "text" | "password" | "number" | "textarea" | "select";
export type AuthType = "apikey" | "oauth2" | "none" | "aws_iam" | "gcp_service_account";

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
 * Get all available providers.
 * Returns a list of all providers that can be configured.
 */
export function getAllProviders(): ModelProvider[] {
    return [
        { id: "anthropic", label: "Anthropic" },
        { id: "bedrock", label: "Amazon Bedrock" },
        { id: "azure_openai", label: "Azure OpenAI" },
        { id: "google_ai_studio", label: "Google AI Studio" },
        { id: "vertex_ai", label: "Google Vertex AI" },
        { id: "ollama", label: "Ollama" },
        { id: "openai", label: "OpenAI" },
        { id: "custom", label: "Custom" },
    ];
}

/**
 * Fetch supported models dynamically from a custom provider endpoint.
 * For other providers, models are fetched from the backend API.
 */
export async function fetchSupportedModels(providerId: string, apiBase?: string, apiKey?: string): Promise<SupportedModel[]> {
    // Only custom providers support dynamic model fetching
    if (providerId === "custom" && apiBase && apiKey) {
        return await fetchModelsFromCustomEndpoint(apiBase, apiKey);
    }

    // For all other providers, return empty array (models come from /api/v1/platform/supported-models)
    return [];
}

/**
 * Fetch models dynamically from an OpenAI-compatible endpoint.
 * Calls {endpoint}/v1/models with the provided API key.
 *
 * @internal - Use fetchSupportedModels() instead
 */
async function fetchModelsFromCustomEndpoint(endpointUrl: string, apiKey: string): Promise<SupportedModel[]> {
    try {
        const baseUrl = endpointUrl.endsWith("/") ? endpointUrl : `${endpointUrl}/`;

        const response = await fetch(`${baseUrl}v1/models`, {
            method: "GET",
            headers: {
                Authorization: `Bearer ${apiKey}`,
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch models: ${response.status}`);
        }

        const data = await response.json();

        // Handle different response formats from various providers
        let modelIds: string[] = [];
        if (data.data && Array.isArray(data.data)) {
            modelIds = data.data.filter((model: ModelResponseItem) => model.id).map((model: ModelResponseItem) => model.id as string);
        } else if (data.models && Array.isArray(data.models)) {
            modelIds = data.models.filter((model: ModelResponseItem) => model.id ?? model.name).map((model: ModelResponseItem) => model.id ?? model.name ?? "");
        } else if (Array.isArray(data)) {
            modelIds = data.filter((model: ModelResponseItem) => model.id ?? model.name).map((model: ModelResponseItem) => model.id ?? (model.name as string));
        }

        return modelIds.map(id => ({ id, label: id }));
    } catch (error) {
        console.error("Error fetching models from custom endpoint:", error);
        return [];
    }
}
