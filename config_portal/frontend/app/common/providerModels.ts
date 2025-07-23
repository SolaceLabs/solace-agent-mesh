export const PROVIDER_ENDPOINTS: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com",
  google: "https://generativelanguage.googleapis.com/v1beta/openai",
  aws: "https://bedrock-runtime.us-east-1.amazonaws.com",
  cohere: "https://api.cohere.ai/compatibility/v1",
};

export const LLM_PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google Gemini" },
  { value: "azure", label: "Azure" },
  { value: "openai_compatible", label: "OpenAI Compatible Provider" },
];
export const PROVIDER_PREFIX_MAP: Record<string, string> = {
  openai: "openai",
  anthropic: "anthropic",
  google: "openai", //using googles open ai compatible endpoint
  openai_compatible: "openai",
  azure: "azure",
};

export const PROVIDER_MODELS: Record<string, string[]> = {
  openai: [
    "o3-mini",
    "o3-mini-high",
    "o3-mini-low",
    "o1",
    "o1-preview",
    "o1-mini",
    "gpt-4.5-preview",
    "gpt-4o",
    "gpt-4o-mini",
  ],
  anthropic: [
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
  ],
  google: [
    "gemini-2.0-flash-001",
    "gemini-2.0-pro-exp-02-05",
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash-thinking-exp-01-21",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro-002",
  ],
  bedrock: [
    "amazon.nova-pro-v1:0",
    "amazon.nova-pro-latency-optimized-v1:0",
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "anthropic.claude-3-7-sonnet-20250219-v1:0",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-3-5-haiku-20241022-v1:0",
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "anthropic.claude-3-opus-20240229-v1:0",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
  ],
  custom: [],
};

export const PROVIDER_NAMES: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Google Vertex AI",
  aws: "AWS Bedrock",
  custom: "Custom Provider",
};

interface Model {
  id?: string;
  name?: string;
}

export async function fetchModelsFromCustomEndpoint(
  endpointUrl: string,
  apiKey: string
): Promise<string[]> {
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

    if (data.data && Array.isArray(data.data)) {
      return data.data
        .filter((model: Model) => model.id)
        .map((model: Model) => model.id);
    } else if (data.models && Array.isArray(data.models)) {
      return data.models
        .filter((model: Model) => model.id ?? model.name)
        .map((model: Model) => model.id ?? model.name);
    } else if (Array.isArray(data)) {
      return data
        .filter((model: Model) => model.id ?? model.name)
        .map((model: Model) => model.id ?? (model.name as string));
    }

    return [];
  } catch (error) {
    console.error("Error fetching models:", error);
    return [];
  }
}

export const formatModelName = (
  modelName: string,
  provider: string
): string => {
  if (modelName.includes("/")) {
    return modelName;
  }

  const providerPrefix = PROVIDER_PREFIX_MAP[provider] || provider;
  return `${providerPrefix}/${modelName}`;
};
