import { useState, useEffect, useCallback } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Button from '../ui/Button';
import ConfirmationModal from '../ui/ConfirmationModal';
import AutocompleteInput from '../ui/AutocompleteInput';
import {
  PROVIDER_ENDPOINTS,
  PROVIDER_MODELS,
  fetchModelsFromCustomEndpoint
} from '../../lib/providerModels';

type AIProviderSetupProps = {
  data: {
    llm_provider: string;
    llm_endpoint_url: string;
    llm_api_key: string;
    llm_model_name: string;
    embedding_endpoint_url: string;
    embedding_api_key: string;
    embedding_model_name: string;
    [key: string]: any
  };
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function AIProviderSetup({ data, updateData, onNext, onPrevious }: AIProviderSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isTestingConfig, setIsTestingConfig] = useState<boolean>(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [showTestErrorDialog, setShowTestErrorDialog] = useState<boolean>(false);
  const [llmModelSuggestions, setLlmModelSuggestions] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState<boolean>(false);
  const [previousProvider, setPreviousProvider] = useState<string | null>(null);

  // Initialize provider if not set
  useEffect(() => {
    if (!data.llm_provider) {
      updateData({ llm_provider: 'openai' });
    }
  }, [data.llm_provider, updateData]);

  // Update endpoint URL and clear model when provider changes
  useEffect(() => {
    if (data.llm_provider) {
      const updates: Record<string, any> = {};
      
      // Only handle provider changes, not every endpoint URL change
      if (previousProvider !== null && previousProvider !== data.llm_provider) {
        // Clear model name when switching providers
        updates.llm_model_name = '';
        
        // Set appropriate endpoint URL based on provider
        if (data.llm_provider !== 'custom' && data.llm_provider !== 'openai_compatible') {
          // For standard providers, set the endpoint URL
          const endpointUrl = PROVIDER_ENDPOINTS[data.llm_provider] || '';
          updates.llm_endpoint_url = endpointUrl;
        } else {
          // For custom provider and OpenAI compatible, clear the endpoint URL
          updates.llm_endpoint_url = '';
        }
        
        // Apply updates
        if (Object.keys(updates).length > 0) {
          updateData(updates);
        }
      }
      
      // Remember current provider for next time
      setPreviousProvider(data.llm_provider);
    }
  }, [data.llm_provider, previousProvider, updateData]);

  // Update model suggestions based on provider
  useEffect(() => {
    if (data.llm_provider && data.llm_provider !== 'custom' && data.llm_provider !== 'openai_compatible') {
      setLlmModelSuggestions(PROVIDER_MODELS[data.llm_provider] || []);
    } else {
      setLlmModelSuggestions([]);
    }
  }, [data.llm_provider]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };

  // Fetch models from custom endpoint
  const fetchCustomModels = useCallback(async () => {
    if ((data.llm_provider === 'custom' || data.llm_provider === 'openai_compatible') &&
        data.llm_endpoint_url && data.llm_api_key) {
      setIsLoadingModels(true);
      try {
        const models = await fetchModelsFromCustomEndpoint(
          data.llm_endpoint_url,
          data.llm_api_key
        );
        setLlmModelSuggestions(models);
      } catch (error) {
        console.error('Error fetching models:', error);
      } finally {
        setIsLoadingModels(false);
      }
    }
    return [];
  }, [data.llm_provider, data.llm_endpoint_url, data.llm_api_key]);
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    // Validate LLM provider
    if (!data.llm_provider) {
      newErrors.llm_provider = 'LLM provider is required';
      isValid = false;
    }
    
    // Validate endpoint URL for custom provider and OpenAI compatible
    if ((data.llm_provider === 'custom' || data.llm_provider === 'openai_compatible') && !data.llm_endpoint_url) {
      newErrors.llm_endpoint_url = `LLM endpoint is required for ${data.llm_provider === 'custom' ? 'custom provider' : 'OpenAI compatible endpoint'}`;
      isValid = false;
    }
    
    if (!data.llm_model_name) {
      newErrors.llm_model_name = 'LLM model name is required';
      isValid = false;
    }

    if(!data.llm_api_key) {
      newErrors.llm_api_key = 'LLM API key is required';
      isValid = false;
    }
    
    if (!data.embedding_endpoint_url) {
      newErrors.embedding_endpoint_url = 'Embedding endpoint is required';
      isValid = false;
    }
    
    if (!data.embedding_model_name) {
      newErrors.embedding_model_name = 'Embedding model name is required';
      isValid = false;
    }

    if(!data.embedding_api_key) {
      newErrors.embedding_api_key = 'Embedding API key is required';
      isValid = false;
    }
    
    // For custom providers, users need to provide the model name with provider prefix
    // following litellm docs: https://docs.litellm.ai/docs/providers
    if (data.llm_provider === 'custom' && data.llm_model_name && !data.llm_model_name.includes('/')) {
      newErrors.llm_model_name = 'For custom providers, model name must follow the format provider/model-name (see litellm docs)';
      isValid = false;
    }
    
    if (data.embedding_model_name && !data.embedding_model_name.includes('/')) {
      newErrors.embedding_model_name = 'Model name should follow the format provider/model-name';
      isValid = false;
    }
    
    setErrors(newErrors);
    return isValid;
  };
  
  // Format model name for litellm
  const formatModelName = (modelName: string, provider: string): string => {
    // For custom provider, always return the model name as is
    // User is expected to provide the full model name with provider prefix
    if (provider === 'custom') {
      return modelName;
    }
    
    // If model name already includes a provider prefix (contains '/'), return as is
    if (modelName.includes('/')) {
      return modelName;
    }
    
    // Map provider names to litellm provider prefixes
    const providerPrefixMap: Record<string, string> = {
      'openai': 'openai',
      'anthropic': 'anthropic',
      'google': 'vertex_ai',
      'aws': 'bedrock',
      'openai_compatible': 'openai'
    };
    
    // Get the correct provider prefix
    const providerPrefix = providerPrefixMap[provider] || provider;
    return `${providerPrefix}/${modelName}`;
  };

  const testLLMConfig = async () => {
    // Exclude certain providers from testing as these require more auth than just a key
    const EXCLUSION_LIST = ['bedrock']
    if (EXCLUSION_LIST.includes(data.llm_provider)) {
      onNext();
      return;
    }
    setIsTestingConfig(true);
    setTestError(null);
    
    try {
      // For standard providers, use the predefined endpoint URL
      // For custom and OpenAI compatible providers, use the user-provided endpoint URL
      const baseUrl = (data.llm_provider !== 'custom' && data.llm_provider !== 'openai_compatible')
        ? PROVIDER_ENDPOINTS[data.llm_provider] || data.llm_endpoint_url
        : data.llm_endpoint_url;
      
      // Format the model name for litellm
      const formattedModelName = formatModelName(data.llm_model_name, data.llm_provider);
      
      const response = await fetch('/api/test_llm_config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: formattedModelName,
          api_key: data.llm_api_key,
          base_url: baseUrl,
        }),
      });
      
      const result = await response.json();
      
      if (result.status === 'success') {
        // Test passed, proceed to next step
        setIsTestingConfig(false);
        onNext();
      } else {
        // Test failed, show error dialog
        setTestError(result.message || 'Failed to test LLM configuration');
        setShowTestErrorDialog(true);
        setIsTestingConfig(false);
      }
    } catch (error) {
      // Handle network or other errors
      setTestError('An error occurred while testing the LLM configuration');
      setShowTestErrorDialog(true);
      setIsTestingConfig(false);
    }
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      testLLMConfig();
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6 ">
        <div className="p-4 bg-blue-50 rounded-md mb-4">
          <p className="text-sm text-blue-800">
            Configure your AI service providers for language models and embeddings.
            Select a provider from the dropdown or choose "Custom Provider" to use your own endpoint.
          </p>
        </div>
        
        <div className="border-b border-gray-200 pb-4 mb-4 ">
          <h3 className="text-lg font-medium mb-4 text-gray-700 font-semibold">Language Model Configuration</h3>
          
          <FormField
            label="LLM Provider"
            htmlFor="llm_provider"
            error={errors.llm_provider}
            required
          >
            <Select
              id="llm_provider"
              name="llm_provider"
              value={data.llm_provider || ''}
              onChange={handleChange}
              options={[
                { value: 'openai', label: 'OpenAI' },
                { value: 'anthropic', label: 'Anthropic' },
                { value: 'google', label: 'Google Vertex AI' },
                { value: 'bedrock', label: 'AWS Bedrock' },
                { value: 'openai_compatible', label: 'OpenAI Compatible' },
                { value: 'custom', label: 'Custom Provider' },
              ]}
            />
          </FormField>
          
          {/* Show endpoint URL for custom provider and OpenAI compatible */}
          {(data.llm_provider === 'custom' || data.llm_provider === 'openai_compatible') && (
            <FormField
              label="LLM Endpoint URL"
              htmlFor="llm_endpoint_url"
              error={errors.llm_endpoint_url}
              required
            >
              <Input
                id="llm_endpoint_url"
                name="llm_endpoint_url"
                value={data.llm_endpoint_url}
                onChange={handleChange}
                placeholder="https://api.example.com/v1"
                autoFocus={true}
              />
            </FormField>
          )}
          
          <FormField
            label="LLM API Key"
            htmlFor="llm_api_key"
            error={errors.llm_api_key}
            required
          >
            <Input
              id="llm_api_key"
              name="llm_api_key"
              type="password"
              value={data.llm_api_key}
              onChange={handleChange}
              placeholder="Enter your API key"
            />
          </FormField>
          
          {data.llm_provider === 'custom' && (
            <div className="p-4 bg-yellow-50 rounded-md mb-4">
              <p className="text-sm text-yellow-800">
                <strong>Important:</strong> For custom providers, you must use the format <code>provider/model-name</code> (e.g., <code>azure/gpt-4</code>)
                following the <a href="https://docs.litellm.ai/docs/providers" target="_blank" rel="noopener noreferrer" className="underline">litellm documentation</a>.
              </p>
            </div>
          )}
          
          <FormField
            label="LLM Model Name"
            htmlFor="llm_model_name"
            error={errors.llm_model_name}
            helpText={
              data.llm_provider === 'custom'
                ? "For custom providers, you must use format: provider/model-name (see litellm docs)"
                : "Select or type a model name"
            }
            required
          >
            <AutocompleteInput
              id="llm_model_name"
              name="llm_model_name"
              value={data.llm_model_name}
              onChange={handleChange}
              placeholder={data.llm_provider === 'custom' ? "provider/model-name (e.g., azure/gpt-4)" : "Select or type a model name"}
              suggestions={llmModelSuggestions}
              onFocus={(data.llm_provider === 'custom' || data.llm_provider === 'openai_compatible') ? fetchCustomModels : undefined}
              showLoadingIndicator={isLoadingModels}
            />
          </FormField>
        </div>
        
        <div>
          <h3 className="text-lg font-medium mb-4 text-gray-700 font-semibold">Embedding Model Configuration</h3>
          
          <FormField 
            label="Embedding Endpoint URL" 
            htmlFor="embedding_endpoint_url"
            error={errors.embedding_endpoint_url}
            required
          >
            <Input
              id="embedding_endpoint_url"
              name="embedding_endpoint_url"
              value={data.embedding_endpoint_url}
              onChange={handleChange}
              placeholder="https://api.example.com/v1"
            />
          </FormField>
          
          <FormField 
            label="Embedding API Key" 
            htmlFor="embedding_api_key"
            error={errors.embedding_api_key}
            required
          >
            <Input
              id="embedding_api_key"
              name="embedding_api_key"
              type="password"
              value={data.embedding_api_key}
              onChange={handleChange}
              placeholder="Enter your API key"
            />
          </FormField>
          
          <FormField 
            label="Embedding Model Name" 
            htmlFor="embedding_model_name"
            helpText="Format: provider/model-name (e.g., openai/text-embedding-ada-002)"
            error={errors.embedding_model_name}
            required
          >
            <Input
              id="embedding_model_name"
              name="embedding_model_name"
              value={data.embedding_model_name}
              onChange={handleChange}
              placeholder="provider/model-name"
            />
          </FormField>
        </div>
      </div>
      
      <div className="mt-8 flex justify-end space-x-4">
        <Button 
          onClick={onPrevious}
          variant="outline"
        >
          Previous
        </Button>
        <Button
          type="submit"
        >
          Next
        </Button>
      </div>

      {/* Loading indicator */}
      {isTestingConfig && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full text-center">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Testing LLM Configuration</h3>
            <div className="flex justify-center mb-4">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-solace-green"></div>
            </div>
            <p>Please wait while we test your LLM configuration...</p>
          </div>
        </div>
      )}
      
      {/* Error dialog */}
      {showTestErrorDialog && (
        <ConfirmationModal
          message={`LLM Configuration Test Failed: ${testError}

This may indicate an issue with your LLM provider settings. Please check your endpoint URL, API key, and model name.

Would you like to ignore this warning and continue anyway?`}
          onConfirm={() => {
            setShowTestErrorDialog(false);
            onNext();
          }}
          onCancel={() => {
            setShowTestErrorDialog(false);
          }}
        />
      )}
    </form>
  );
}