// Provider to endpoint URL mapping
export const PROVIDER_ENDPOINTS: Record<string, string> = {
  "openai": "https://api.openai.com/v1",
  "anthropic": "https://api.anthropic.com",
  "google": "https://generativelanguage.googleapis.com/v1beta/openai",
  "aws": "https://bedrock-runtime.us-east-1.amazonaws.com",
  "cohere": "https://api.cohere.ai/compatibility/v1",
};

// in case we use providers that image only or their url's are different than llm endpoints
// export const IMAGE_GEN_PROVIDER_ENDPOINTS: Record<string, string> = {
//   "openai": "https://api.openai.com/v1",
//   //"google": "https://generativelanguage.googleapis.com",
// }

export const LLM_PROVIDER_OPTIONS = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'google', label: 'Google Gemini' },
    { value: 'azure', label: 'Azure' },
    { value: 'openai_compatible', label: 'OpenAI Compatible Provider' },
  ]

export const EMBEDDING_PROVIDER_OPTIONS = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'google', label: 'Google Gemini' },
    { value: 'cohere', label: 'Cohere' },
    { value: 'openai_compatible', label: 'OpenAI Compatible Provider' },
  ]
  
  // Map provider names to litellm provider prefixes
export const PROVIDER_PREFIX_MAP: Record<string, string> = {
    'openai': 'openai',
    'anthropic': 'anthropic',
    'google': 'openai', //using googles open ai compatible endpoint
    'openai_compatible': 'openai',
    'azure': 'azure',
  };

  // Map embedding provider names to litellm provider prefixes
export const EMBEDDING_PROVIDER_PREFIX_MAP: Record<string, string> = {
    'openai': 'openai',
    'google': 'openai',
    'cohere': 'cohere',
    'openai_compatible': 'openai',
  };

  // Embedding model options by provider
export const EMBEDDING_PROVIDER_MODELS: Record<string, string[]> = {
    'openai': [
      'text-embedding-3-small', 
      'text-embedding-3-large',
      'text-embedding-ada-002'
    ],
    'google': [
      'gemini-embedding-exp-03-07',
    ],
    'cohere': [
      'embed-english-v3.0',
      'embed-multilingual-v3.0',
      'embed-english-light-v3.0',
      'embed-multilingual-light-v3.0'
    ],
    'openai_compatible': []
  };

// Image Generation Provider Options
export const IMAGE_GEN_PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  //{ value: 'google', label: 'Google' },
  { value: 'openai_compatible', label: 'OpenAI Compatible Provider' },
];

// Image Generation Provider Prefix Map
export const IMAGE_GEN_PROVIDER_PREFIX_MAP: Record<string, string> = {
  'openai': 'openai',
  'google': 'gemini',
  'openai_compatible': 'openai',
};

// Image Generation Models by Provider
export const IMAGE_GEN_PROVIDER_MODELS: Record<string, string[]> = {
  'openai': [
    'dall-e-3',
    'dall-e-2',
  ],
  'google': [
    'imagen-3',
    'imagen-2',
  ],
  'openai_compatible': []
};

// Provider to models mapping
export const PROVIDER_MODELS: Record<string, string[]> = {
  "openai": [
    "o3-mini", 
    "o3-mini-high", 
    "o3-mini-low", 
    "o1", 
    "o1-preview", 
    "o1-mini",
    "gpt-4.5-preview", 
    "gpt-4o", 
    "gpt-4o-mini"
  ],
  "anthropic": [
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022", 
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229", 
    "claude-3-haiku-20240307"
  ],
  "google": [
    "gemini-2.0-flash-001", 
    "gemini-2.0-pro-exp-02-05", 
    "gemini-2.0-flash-lite-001",
    "gemini-2.0-flash-thinking-exp-01-21", 
    "gemini-1.5-flash-002", 
    "gemini-1.5-pro-002"
  ],
  "bedrock": [
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
    "anthropic.claude-3-haiku-20240307-v1:0"
  ],
  "custom": []
};

// Provider display names
export const PROVIDER_NAMES: Record<string, string> = {
  "openai": "OpenAI",
  "anthropic": "Anthropic",
  "google": "Google Vertex AI",
  "aws": "AWS Bedrock",
  "custom": "Custom Provider"
};

// Function to fetch models from a custom endpoint
export async function fetchModelsFromCustomEndpoint(
  endpointUrl: string, 
  apiKey: string
): Promise<string[]> {
  try {
    // Ensure the endpoint URL ends with a slash
    const baseUrl = endpointUrl.endsWith('/') ? endpointUrl : `${endpointUrl}/`;
    
    // Make the API call to fetch models
    const response = await fetch(`${baseUrl}v1/models`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch models: ${response.status}`);
    }

    const data = await response.json();
    
    // Handle different API response formats
    if (data.data && Array.isArray(data.data)) {
      // Format like Anthropic's API
      return data.data
        .filter((model: any) => model.id)
        .map((model: any) => model.id);
    } else if (data.models && Array.isArray(data.models)) {
      // Format with models array
      return data.models
        .filter((model: any) => model.id ?? model.name)
        .map((model: any) => model.id ?? model.name);
    } else if (Array.isArray(data)) {
      // Format with direct array
      return data
        .filter((model: any) => model.id ?? model.name)
        .map((model: any) => model.id ?? model.name);
    }
    
    // Fallback: return empty array if format is not recognized
    return [];
  } catch (error) {
    console.error('Error fetching models:', error);
    return [];
  }
}

  // Format model name for litellm
  export const formatModelName = (modelName: string, provider: string): string => {
  
    // If model name already includes a provider prefix (contains '/'), return as is
    if (modelName.includes('/')) {
      return modelName;
    }
        
    // Get the correct provider prefix
    const providerPrefix = PROVIDER_PREFIX_MAP[provider] || provider;
    return `${providerPrefix}/${modelName}`;
  };