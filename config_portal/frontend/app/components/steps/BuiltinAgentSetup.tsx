import { useState, useEffect } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Toggle from '../ui/Toggle';
import Button from '../ui/Button';
import { InfoBox } from '../ui/InfoBoxes';
import Select from '../ui/Select';
import AutocompleteInput from '../ui/AutocompleteInput';
import {
  IMAGE_GEN_PROVIDER_OPTIONS,
  IMAGE_GEN_PROVIDER_MODELS,
  PROVIDER_ENDPOINTS
} from '../../common/providerModels';

// Configuration for agent names and descriptions
export const BUILTIN_AGENTS = {
  webRequest: {
    id: 'web_request',
    name: 'Web Request Agent',
    description: 'Can make queries to web to get real-time data'
  },
  imageProcessing: {
    id: 'image_processing',
    name: 'Image Processing Agent',
    description: 'Generate images from text or convert images to text'
  }
};

// Configuration for image agent environment variable keys
const IMAGE_AGENT_ENV_VARS = {
  provider: 'IMAGE_GEN_PROVIDER',
  endpoint: 'IMAGE_GEN_ENDPOINT',
  apiKey: 'IMAGE_GEN_API_KEY',
  model: 'IMAGE_GEN_MODEL'
};

type BuiltinAgentSetupProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function BuiltinAgentSetup({ 
  data, 
  updateData, 
  onNext, 
  onPrevious 
}: Readonly<BuiltinAgentSetupProps>) {
  // Configuration for enabled/disabled agents
  const [enabledAgents, setEnabledAgents] = useState<string[]>(data.built_in_agent ?? []);
  
  // Environment variables state
  const [environmentVariables, setEnvironmentVariables] = useState<Record<string, string>>({});
  
  // Validation errors
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  
  // Image generation model suggestions based on provider
  const [imageModelSuggestions, setImageModelSuggestions] = useState<string[]>([]);

  // Convert the environment variables to the format expected by the parent component
  const updateParentWithFormattedEnvVars = (environmentVarObject: Record<string, string>) => {
    const environmentVariablePairs = Object.entries(environmentVarObject);
    
    //Filter out any entries with empty values
    const nonEmptyEnvironmentVariables = environmentVariablePairs.filter(
      ([_, value]) => value !== ''
    );
    
    //Format each pair as "KEY=value" string
    const formattedEnvironmentVariables = nonEmptyEnvironmentVariables.map(
      ([key, value]) => `${key}=${value}`
    );

    updateData({
      env_var: formattedEnvironmentVariables
    });
  };

  // Initialize form data from existing configuration
  useEffect(() => {
    const initialEnvironmentVariables: Record<string, string> = {};
    
    // Parse existing env_var data if present
    if (data.env_var && Array.isArray(data.env_var)) {
      data.env_var.forEach((envVar: string) => {
        if (envVar.includes('=')) {
          const [key, value] = envVar.split('=');
          initialEnvironmentVariables[key] = value;
        }
      });
    }
    
    // Set default values for image processing if enabled
    if (enabledAgents.includes(BUILTIN_AGENTS.imageProcessing.id)) {
      // Set default provider if not set
      if (!initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.provider]) {
        initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.provider] = 'openai';
      }
      
      // Set default endpoint if not set and not using openai_compatible
      const currentProvider = initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.provider];
      if (!initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] && 
          currentProvider !== 'openai_compatible') {
        initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] = PROVIDER_ENDPOINTS[currentProvider] || '';
      }
      
      // Ensure API key exists
      if (!initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.apiKey]) {
        initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.apiKey] = '';
      }
      
      // Ensure model exists
      if (!initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.model]) {
        initialEnvironmentVariables[IMAGE_AGENT_ENV_VARS.model] = '';
      }
      
      // Initialize model suggestions based on provider
      if (currentProvider && currentProvider !== 'openai_compatible') {
        setImageModelSuggestions(IMAGE_GEN_PROVIDER_MODELS[currentProvider] || []);
      }
    }
    
    setEnvironmentVariables(initialEnvironmentVariables);
  }, [data.env_var]);
  
  // Update environment variable and propagate to parent
  const updateEnvironmentVariable = (key: string, value: string) => {
    const newEnvironmentVariables = {
      ...environmentVariables,
      [key]: value
    };
    
    setEnvironmentVariables(newEnvironmentVariables);
    
    // Clear any validation error for this field
    if (validationErrors[key]) {
      setValidationErrors({
        ...validationErrors,
        [key]: ''
      });
    }
    
    // Convert to env_var array format and update parent
    updateParentWithFormattedEnvVars(newEnvironmentVariables);
  };
  
  // Toggle agent enabled/disabled
  const toggleAgent = (agentId: string, enabled: boolean) => {
    let updatedAgents: string[];
    
    if (enabled) {
      updatedAgents = enabledAgents.includes(agentId) 
        ? enabledAgents 
        : [...enabledAgents, agentId];
      
      // Initialize Image Processing fields when enabled
      if (agentId === BUILTIN_AGENTS.imageProcessing.id && 
          !enabledAgents.includes(BUILTIN_AGENTS.imageProcessing.id)) {
        const newEnvironmentVariables = { ...environmentVariables };
        const defaultProvider = 'openai';
        
        // Initialize with default values
        newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.provider] = defaultProvider;
        newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] = PROVIDER_ENDPOINTS[defaultProvider] || '';
        newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.apiKey] = '';
        newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.model] = '';
        
        setEnvironmentVariables(newEnvironmentVariables);
        setImageModelSuggestions(IMAGE_GEN_PROVIDER_MODELS[defaultProvider] || []);
        
        // Update parent with env vars
        updateParentWithFormattedEnvVars(newEnvironmentVariables);
      }
    } else {
      updatedAgents = enabledAgents.filter(id => id !== agentId);
      
      // Clear image processing fields when disabled
      if (agentId === BUILTIN_AGENTS.imageProcessing.id) {
        const newEnvironmentVariables = { ...environmentVariables };
        const newValidationErrors = { ...validationErrors };
        
        // Loop through and remove all image processing environment variables
        Object.values(IMAGE_AGENT_ENV_VARS).forEach(key => {
          delete newEnvironmentVariables[key];
          delete newValidationErrors[key];
        });
        
        setEnvironmentVariables(newEnvironmentVariables);
        setValidationErrors(newValidationErrors);
        
        // Update parent with cleaned env vars
        updateParentWithFormattedEnvVars(newEnvironmentVariables);
      }
    }
    
    setEnabledAgents(updatedAgents);
    updateData({ built_in_agent: updatedAgents });
  };
  
  // Handle image provider change
  const handleImageProviderChange = (provider: string) => {
    const newEnvironmentVariables = {
      ...environmentVariables,
      [IMAGE_AGENT_ENV_VARS.provider]: provider,
      [IMAGE_AGENT_ENV_VARS.model]: ''
    };
    
    // Update endpoint for standard providers or clear for custom
    if (provider !== 'openai_compatible') {
      newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] = PROVIDER_ENDPOINTS[provider] || '';
      setImageModelSuggestions(IMAGE_GEN_PROVIDER_MODELS[provider] || []);
    } else {
      newEnvironmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] = '';
      setImageModelSuggestions([]);
    }
    
    // Update state all at once
    setEnvironmentVariables(newEnvironmentVariables);
    
    // Clear any validation errors
    const keysToUpdate = [
      IMAGE_AGENT_ENV_VARS.provider,
      IMAGE_AGENT_ENV_VARS.model,
      IMAGE_AGENT_ENV_VARS.endpoint
    ];
    
    const newValidationErrors = { ...validationErrors };
    keysToUpdate.forEach(key => {
      if (newValidationErrors[key]) {
        delete newValidationErrors[key];
      }
    });
    
    if (Object.keys(newValidationErrors).length !== Object.keys(validationErrors).length) {
      setValidationErrors(newValidationErrors);
    }
    
    // Update parent data with the new environment variables
    updateParentWithFormattedEnvVars(newEnvironmentVariables);
  };
  
  // Form validation
  const validateForm = () => {
    const newValidationErrors: Record<string, string> = {};
    let isValid = true;
    
    // Validate Image Processing Agent
    if (enabledAgents.includes(BUILTIN_AGENTS.imageProcessing.id)) {
      // Validate provider
      if (!environmentVariables[IMAGE_AGENT_ENV_VARS.provider]) {
        newValidationErrors[IMAGE_AGENT_ENV_VARS.provider] = 'Image Generation Provider is required';
        isValid = false;
      }
      
      // Validate endpoint for custom provider
      if (environmentVariables[IMAGE_AGENT_ENV_VARS.provider] === 'openai_compatible' && 
          !environmentVariables[IMAGE_AGENT_ENV_VARS.endpoint]) {
        newValidationErrors[IMAGE_AGENT_ENV_VARS.endpoint] = 'Image Generation Endpoint is required';
        isValid = false;
      }
      
      // Validate API key
      if (!environmentVariables[IMAGE_AGENT_ENV_VARS.apiKey]) {
        newValidationErrors[IMAGE_AGENT_ENV_VARS.apiKey] = 'Image Generation API Key is required';
        isValid = false;
      }
      
      // Validate model name
      if (!environmentVariables[IMAGE_AGENT_ENV_VARS.model]) {
        newValidationErrors[IMAGE_AGENT_ENV_VARS.model] = 'Image Generation Model is required';
        isValid = false;
      }
    }
    
    setValidationErrors(newValidationErrors);
    return isValid;
  };
  
  // Form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onNext();
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <InfoBox className="mb-4">
          Enable and configure built-in agents to extend your system's capabilities.
        </InfoBox>
        
        {/* Web Request Agent */}
        <div className="flex flex-col p-4 border border-gray-200 rounded-md">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-solace-blue">{BUILTIN_AGENTS.webRequest.name}</h3>
              <p className="text-sm text-gray-500">{BUILTIN_AGENTS.webRequest.description}</p>
            </div>
            <Toggle
              id={`toggle_${BUILTIN_AGENTS.webRequest.id}`}
              checked={enabledAgents.includes(BUILTIN_AGENTS.webRequest.id)}
              onChange={(checked) => toggleAgent(BUILTIN_AGENTS.webRequest.id, checked)}
            />
          </div>
        </div>
        
        {/* Image Processing Agent */}
        <div className="flex flex-col p-4 border border-gray-200 rounded-md">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium text-solace-blue">{BUILTIN_AGENTS.imageProcessing.name}</h3>
              <p className="text-sm text-gray-500">{BUILTIN_AGENTS.imageProcessing.description}</p>
            </div>
            <Toggle
              id={`toggle_${BUILTIN_AGENTS.imageProcessing.id}`}
              checked={enabledAgents.includes(BUILTIN_AGENTS.imageProcessing.id)}
              onChange={(checked) => toggleAgent(BUILTIN_AGENTS.imageProcessing.id, checked)}
            />
          </div>
          
          {/* Show configuration fields when enabled */}
          {enabledAgents.includes(BUILTIN_AGENTS.imageProcessing.id) && (
            <div className="space-y-4 mt-4 pt-4 border-t border-gray-200">
              {/* Provider selection */}
              <FormField
                label="Image Generation Provider"
                htmlFor={IMAGE_AGENT_ENV_VARS.provider}
                error={validationErrors[IMAGE_AGENT_ENV_VARS.provider]}
                required
              >
                <Select
                  id={IMAGE_AGENT_ENV_VARS.provider}
                  name={IMAGE_AGENT_ENV_VARS.provider}
                  value={environmentVariables[IMAGE_AGENT_ENV_VARS.provider] || ''}
                  onChange={(e) => handleImageProviderChange(e.target.value)}
                  options={IMAGE_GEN_PROVIDER_OPTIONS}
                />
              </FormField>
              
              {/* Endpoint URL - only for OpenAI compatible */}
              {environmentVariables[IMAGE_AGENT_ENV_VARS.provider] === 'openai_compatible' && (
                <FormField
                  label="Image Generation Endpoint"
                  htmlFor={IMAGE_AGENT_ENV_VARS.endpoint}
                  error={validationErrors[IMAGE_AGENT_ENV_VARS.endpoint]}
                  required
                >
                  <Input
                    id={IMAGE_AGENT_ENV_VARS.endpoint}
                    name={IMAGE_AGENT_ENV_VARS.endpoint}
                    type="text"
                    value={environmentVariables[IMAGE_AGENT_ENV_VARS.endpoint] || ''}
                    onChange={(e) => updateEnvironmentVariable(IMAGE_AGENT_ENV_VARS.endpoint, e.target.value)}
                    placeholder="Enter endpoint URL"
                  />
                </FormField>
              )}
              
              {/* API Key */}
              <FormField
                label="Image Generation API Key"
                htmlFor={IMAGE_AGENT_ENV_VARS.apiKey}
                error={validationErrors[IMAGE_AGENT_ENV_VARS.apiKey]}
                required
              >
                <Input
                  id={IMAGE_AGENT_ENV_VARS.apiKey}
                  name={IMAGE_AGENT_ENV_VARS.apiKey}
                  type="password"
                  value={environmentVariables[IMAGE_AGENT_ENV_VARS.apiKey] || ''}
                  onChange={(e) => updateEnvironmentVariable(IMAGE_AGENT_ENV_VARS.apiKey, e.target.value)}
                  placeholder="Enter API key"
                />
              </FormField>
              
              {/* Model selection */}
              <FormField
                label="Image Generation Model"
                htmlFor={IMAGE_AGENT_ENV_VARS.model}
                error={validationErrors[IMAGE_AGENT_ENV_VARS.model]}
                required
              >
                <AutocompleteInput
                  id={IMAGE_AGENT_ENV_VARS.model}
                  name={IMAGE_AGENT_ENV_VARS.model}
                  value={environmentVariables[IMAGE_AGENT_ENV_VARS.model] || ''}
                  onChange={(e) => updateEnvironmentVariable(IMAGE_AGENT_ENV_VARS.model, e.target.value)}
                  placeholder="Select or type a model name"
                  suggestions={imageModelSuggestions}
                  onFocus={() => {
                    const provider = environmentVariables[IMAGE_AGENT_ENV_VARS.provider] || 'openai';
                    if (provider && provider !== 'openai_compatible') {
                      setImageModelSuggestions(IMAGE_GEN_PROVIDER_MODELS[provider] || []);
                    }
                  }}
                />
              </FormField>
            </div>
          )}
        </div>
      </div>
      
      <div className="mt-8 flex justify-end space-x-4">
        <Button 
          onClick={onPrevious}
          variant="outline"
          type="button"
        >
          Previous
        </Button>
        <Button 
          type="submit"
        >
          Next
        </Button>
      </div>
    </form>
  );
}