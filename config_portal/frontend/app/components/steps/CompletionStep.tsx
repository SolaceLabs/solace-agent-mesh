import { useState, useMemo } from 'react';
import Button from '../ui/Button';
import { builtinAgents } from './BuiltinAgentSetup';
import {
  PROVIDER_PREFIX_MAP,
  EMBEDDING_PROVIDER_PREFIX_MAP,
  IMAGE_GEN_PROVIDER_PREFIX_MAP,
  LLM_PROVIDER_OPTIONS,
} from '../../common/providerModels';

type CompletionStepProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onPrevious: () => void;
};

// Words that should always be capitalized
const CAPITALIZED_WORDS = ['llm', 'ai', 'api', 'url', 'vpn'];

// Sensitive fields that should be hidden
const SENSITIVE_FIELDS = ['broker_password', 'llm_api_key', 'embedding_api_key'];
// Group configuration items by category
const CONFIG_GROUPS: Record<string, string[]> = {
  Project: ['namespace'],
  Broker: ['broker_type'],
  'AI Providers': [
    'llm_model_name',
    'llm_endpoint_url',
    'llm_api_key',
    'embedding_model_name',
    'embedding_endpoint_url',
    'embedding_api_key',
  ],
  'Built-in Agents': ['built_in_agent'],
  'File Service': ['file_service_provider', 'file_service_config'],
};

export default function CompletionStep({ data, updateData, onPrevious }: Readonly<CompletionStepProps>) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Create a mapping of agent IDs to their information
  const agentMapping = useMemo(() => {
    const mapping: Record<
      string,
      { name: string; envVars?: string[] }
    > = {};
    builtinAgents.forEach((agent) => {
      mapping[agent.id] = {
        name: agent.name,
        envVars: agent.envVars?.map((env) => env.key),
      };
    });
    return mapping;
  }, []);

  //  Helper Functions
  /** Check if a given value is considered "empty". */
  const isValueEmpty = (value: any) => {
    return (
      value === undefined ||
      value === '' ||
      (Array.isArray(value) && value.length === 0)
    );
  };

  /** Format a key's label by splitting underscores and capitalizing certain words. */
  const formatDisplayLabel = (key: string): string => {
    return key
      .split('_')
      .map((word) => {
        if (CAPITALIZED_WORDS.includes(word.toLowerCase())) {
          return word.toUpperCase();
        }
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(' ');
  };

  /** Obscure sensitive values or display as text. */
  const formatValue = (key: string, value: any): string => {
    if (
      SENSITIVE_FIELDS.includes(key) ||
      key.toUpperCase().includes('API_KEY')
    ) {
      return value && value.length > 0 ? '••••••••' : 'Not provided';
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    return value && value.toString().length > 0
      ? value.toString()
      : 'Not provided';
  };

  /** Return descriptive text for a broker type. */
  const getBrokerTypeText = (type: string) => {
    switch (type) {
      case 'solace':
        return 'Existing Solace Pub/Sub+ broker';
      case 'container':
        return 'New local Solace PubSub+ broker container (podman/docker)';
      case 'dev_mode':
        return "Run in 'dev mode' - all in one process (not recommended for production)";
      default:
        return type;
    }
  };

  /** Render broker details if needed. */
  const renderBrokerDetails = () => {
    const type = data.broker_type;
    if (!type) return null;

    return (
      <div>
        <div className="mb-1">
          <span className="text-gray-600">Type:</span>
          <span className="font-medium text-gray-900 ml-2">{getBrokerTypeText(type)}</span>
        </div>
        
        {type === 'container' && (
          <div className="pl-4 border-l-2 border-gray-300 mb-2">
            <div className="flex mb-1">
              <span className="text-gray-600">Container Engine:</span>
              <span className="font-medium text-gray-900 ml-2">{data.container_engine ?? 'Docker'}</span>
            </div>
          </div>
        )}
        
        {(type === 'solace' || type === 'container') && (
          <div className="pl-4 border-l-2 border-gray-300">
            <div className="flex mb-1">
              <span className="text-gray-600">Broker URL:</span>
              <span className="font-medium text-gray-900 ml-2">{data.broker_url}</span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Broker VPN:</span>
              <span className="font-medium text-gray-900 ml-2">{data.broker_vpn}</span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Username:</span>
              <span className="font-medium text-gray-900 ml-2">{data.broker_username}</span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Password:</span>
              <span className="font-medium text-gray-900 ml-2">{formatValue('broker_password', data.broker_password)}</span>
            </div>
          </div>
        )}
      </div>
    );
  };
  /** Render built-in agents. */
  const renderBuiltInAgents = (agentIds: string[]) => {
    return (
      <div className="space-y-2 pl-1">
        {agentIds.map((agentId: string) => {
          const agentInfo = agentMapping[agentId] || { name: agentId };
          return (
            <div key={agentId} className="flex items-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 text-green-600 mr-2"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <span className="font-medium text-gray-900">{agentInfo.name}</span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  /** Render file service configuration. */
  const renderFileServiceConfig = (configArray: string[]) => {
    const isVolume = configArray.some((conf) => conf.startsWith('directory='));
    const isBucket = configArray.some((conf) => conf.startsWith('bucket_name='));
    if (isVolume) {
      const volumePath = configArray
        .find((conf) => conf.startsWith('directory='))
        ?.split('=')[1];
      return (
        <div className="pl-4 border-l-2 border-gray-300">
          <div className="flex mb-1">
            <span className="text-gray-600">Volume Path:</span>
            <span className="font-medium text-gray-900 ml-2">{volumePath}</span>
          </div>
        </div>
      );
    }
    if (isBucket) {
      const bucketName = configArray
        .find((conf) => conf.startsWith('bucket_name='))
        ?.split('=')[1];
      const endpointUrl = configArray
        .find((conf) => conf.startsWith('endpoint_url='))
        ?.split('=')[1];
      return (
        <div className="pl-4 border-l-2 border-gray-300">
          <div className="flex mb-1">
            <span className="text-gray-600">Bucket Name:</span>
            <span className="font-medium text-gray-900 ml-2">{bucketName}</span>
          </div>
          <div className="flex mb-1">
            <span className="text-gray-600">Endpoint URL:</span>
            <span className="font-medium text-gray-900 ml-2">{endpointUrl}</span>
          </div>
        </div>
      );
    }
    // Otherwise just display a joined list
    return (
      <div className="font-medium text-gray-900">
        {configArray.join(', ')}
      </div>
    );
  };

  /** Helper function to get provider label from value */
  const getProviderLabel = (providerValue: string): string => {
    const provider = LLM_PROVIDER_OPTIONS.find(p => p.value === providerValue);
    return provider ? provider.label : providerValue;
  };

  /** Render a single group (e.g. "Broker", "LLM Providers"). */
  const renderGroup = (groupName: string, keys: string[]) => {
    // Check if there's at least one non-empty value in the group
    const hasValues = keys.some((key) => !isValueEmpty(data[key]));
    
    if (!hasValues) return null;
    
    // Special handling for AI Providers section
    if (groupName === 'AI Providers') {
      return (
        <div
          key={groupName}
          className="pb-4 mb-4 border-b border-gray-300 last:border-0 last:mb-0 last:pb-0"
        >
          <h4 className="font-semibold text-solace-blue mb-3">{groupName}</h4>
          <div className="space-y-3">
            {/* LLM Model and Provider - common for both quick and advanced */}
            {data.llm_model_name && (
              <div className="flex mb-1">
                <span className="text-gray-600">LLM Model Name:</span>
                <span className="font-medium text-gray-900 ml-2">{data.llm_model_name}</span>
              </div>
            )}
            
            {data.llm_provider && (
              <div className="flex mb-1">
                <span className="text-gray-600">LLM Provider:</span>
                <span className="font-medium text-gray-900 ml-2">{getProviderLabel(data.llm_provider)}</span>
              </div>
            )}
            
            {/* Show endpoint URL only if provider is openai_compatible */}
            {data.llm_provider === "openai_compatible" && data.llm_endpoint_url && (
              <div className="flex mb-1">
                <span className="text-gray-600">LLM Endpoint URL:</span>
                <span className="font-medium text-gray-900 ml-2">{data.llm_endpoint_url}</span>
              </div>
            )}
            
            {/* LLM API Key - show in both quick and advanced setup */}
            {data.llm_api_key && (
              <div className="flex mb-1">
                <span className="text-gray-600">LLM API Key:</span>
                <span className="font-medium text-gray-900 ml-2">
                  {formatValue('llm_api_key', data.llm_api_key)}
                </span>
              </div>
            )}
            
            {/* For advanced mode, show embedding details */}
            {data.setupPath === "advanced" && (
              <>              
                {/* Only show embedding details if embedding_service_enabled is true */}
                {data.embedding_service_enabled === true && (
                  <>
                    {data.embedding_model_name && (
                      <div className="flex mb-1">
                        <span className="text-gray-600">Embedding Model Name:</span>
                        <span className="font-medium text-gray-900 ml-2">{data.embedding_model_name}</span>
                      </div>
                    )}
                    
                    {data.embedding_provider && (
                      <div className="flex mb-1">
                        <span className="text-gray-600">Embedding Provider:</span>
                        <span className="font-medium text-gray-900 ml-2">{getProviderLabel(data.embedding_provider)}</span>
                      </div>
                    )}
                    
                    {/* Show embedding endpoint URL only if provider is openai_compatible */}
                    {data.embedding_provider === "openai_compatible" && data.embedding_endpoint_url && (
                      <div className="flex mb-1">
                        <span className="text-gray-600">Embedding Endpoint URL:</span>
                        <span className="font-medium text-gray-900 ml-2">{data.embedding_endpoint_url}</span>
                      </div>
                    )}
                    
                    {data.embedding_api_key && (
                      <div className="flex mb-1">
                        <span className="text-gray-600">Embedding API Key:</span>
                        <span className="font-medium text-gray-900 ml-2">
                          {formatValue('embedding_api_key', data.embedding_api_key)}
                        </span>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      );
    }
  
    // Standard rendering for other groups
    return (
      <div
        key={groupName}
        className="pb-4 mb-4 border-b border-gray-300 last:border-0 last:mb-0 last:pb-0"
      >
        <h4 className="font-semibold text-solace-blue mb-3">{groupName}</h4>
        <div className="space-y-3">
          {keys.map((key) => {
            if (isValueEmpty(data[key])) return null;
            
            // Special handling for certain keys
            if (key === 'broker_type') return <div key={key}>{renderBrokerDetails()}</div>;
            if (key === 'built_in_agent' && Array.isArray(data[key])) {
              return (
                <div key={key}>
                  {renderBuiltInAgents(data[key])}
                </div>
              );
            }
            if (key === 'file_service_config' && Array.isArray(data[key])) {
              return (
                <div key={key}>
                  {renderFileServiceConfig(data[key])}
                </div>
              );
            }
            
            // Default display
            return (
              <div key={key} className="flex mb-1">
                <span className="text-gray-600">{formatDisplayLabel(key)}:</span>
                <span className="font-medium text-gray-900 ml-2">{formatValue(key, data[key])}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  //this helper clears out all the UI state that is not needed before submitting
  //TODO: Use context provider to pass this data around.
  const cleanDataBeforeSubmit = (data: Record<string, any>) => {
    // if namespace does not end with / add it
    if (data.namespace && !data.namespace.endsWith('/')) {
      data.namespace += '/';
    }
    if (data.container_started){
      //remove container_started from data
      delete data.container_started;
    }

    // first dereference the providers to the actual prefixes
    if (data.llm_provider) {
      data.llm_provider = PROVIDER_PREFIX_MAP[data.llm_provider];
    }
    if (data.embedding_provider) {
      data.embedding_provider = EMBEDDING_PROVIDER_PREFIX_MAP[data.embedding_provider];
    }
    
    //join provider and model name
    if (data.llm_model_name && data.llm_provider){
      data.llm_model_name = `${data.llm_provider}/${data.llm_model_name}`;
      delete data.llm_provider
    }

    // if embedding service is not enabled, put empty strings for embedding fields
    if (!data.embedding_service_enabled){
      data.embedding_api_key = "";
      data.embedding_model_name = "";
      data.embedding_endpoint_url = "";
      
    }
    if (data.embedding_model_name && data.embedding_provider){
      data.embedding_model_name = `${data.embedding_provider}/${data.embedding_model_name}`;
      delete data.embedding_provider
    }

    // Handle image generation provider and model in env_var
    if (data.env_var && Array.isArray(data.env_var)) {
      let imageGenProvider = '';
      let imageGenModel = '';
      
      // Extract provider and model from env_var
      data.env_var.forEach((env: string) => {
        if (env.startsWith('IMAGE_GEN_PROVIDER=')) {
          imageGenProvider = env.split('=')[1];
        }
        if (env.startsWith('IMAGE_GEN_MODEL=')) {
          imageGenModel = env.split('=')[1];
        }
      });
      
      // If both provider and model exist, format and update
      if (imageGenProvider && imageGenModel) {
        // Get the provider prefix
        const providerPrefix = IMAGE_GEN_PROVIDER_PREFIX_MAP[imageGenProvider] || imageGenProvider;
        
        // Format the model name
        const formattedModel = `${providerPrefix}/${imageGenModel}`;
        
        // Update env_var array
        data.env_var = data.env_var.map((env: string) => {
          if (env.startsWith('IMAGE_GEN_MODEL=')) {
            return `IMAGE_GEN_MODEL=${formattedModel}`;
          }
          if (env.startsWith('IMAGE_GEN_PROVIDER=')) {
            return null;
          }
          return env;
        }).filter(Boolean);
      }
    }
  };

  //  Submission Logic
  // TODO: Ask confirmation before overwriting REST API files this function allows for it but we have other ui issues to handle before this can be implemented
  const submitConfiguration = async (force = true) => {
    cleanDataBeforeSubmit(data);
    console.log('Submitting configuration:', data);
    try {
      const response = await fetch('api/save_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(force ? { ...data, force: true } : data),
      });

      const result = await response.json();
           
      if (!response.ok) {
        throw new Error(
          `HTTP error ${response.status}: ${result.message ?? 'Unknown error'}`
        );
      }
      
      if (result.status === 'success') {
        console.log('Configuration sent successfully!');
        
        // Signal to parent to show success screen
        updateData({ showSuccess: true });
        
        try {
          const shutdownResponse = await fetch('api/shutdown', {
            method: 'POST',
          });
          if (!shutdownResponse.ok) {
            console.warn('Shutdown request failed:', shutdownResponse.status);
          } else {
            console.log('Shutdown request sent successfully');
          }
        } catch (shutdownError) {
          console.error('Error sending shutdown request:', shutdownError);
        }
      } else {
        throw new Error(result.message ?? 'Failed to save configuration');
      }
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'An unknown error occurred'
      );
      console.error('Error saving configuration:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    await submitConfiguration();
  };

  // Handle form submission
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  //  Rendering
  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit}>
        <div className="bg-gray-100 border border-gray-300 rounded-md p-5 space-y-4">
          {data.setupPath === "quick" ? (
            // In quick mode, only render the "AI Providers" section
            renderGroup('AI Providers', CONFIG_GROUPS['AI Providers'])
          ) : (
            // In advanced mode, render all sections
            Object.entries(CONFIG_GROUPS).map(([groupName, keys]) =>
              renderGroup(groupName, keys)
            )
          )}
        </div>
        {submitError && (
          <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
            <p className="font-medium">Error initializing project</p>
            <p>{submitError}</p>
          </div>
        )}
        <div className="mt-8 flex justify-end space-x-4">
          <Button onClick={onPrevious} variant="outline" type="button">
            Previous
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <div className="flex items-center space-x-2">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Initializing...</span>
              </div>
            ) : 'Initialize Project'}
          </Button>
        </div>
      </form>
    </div>
  );
}