import { useState, useMemo } from 'react';
import Button from '../ui/Button';
import ConfirmationModal from '../ui/ConfirmationModal';
import { builtinAgents } from './BuiltinAgentSetup';
import SuccessScreen from './SuccessScreen';

type CompletionStepProps = {
  data: Record<string, any>;
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

export default function CompletionStep({ data, onPrevious }: CompletionStepProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [confirmationMessage, setConfirmationMessage] = useState('');

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
      <div className="text-gray-700">
        Type: {getBrokerTypeText(type)}
        {type === 'container' && (
          <div className="pl-4 border-l-2 border-gray-200">
            <div className="ml-2">
              Container Engine: {data.container_engine || 'Docker'}
            </div>
          </div>
        )}
        {(type === 'solace' || type === 'container') && (
          <div className="pl-4 border-l-2 border-gray-200">
            <div className="ml-2">Broker URL: {data.broker_url}</div>
            <div className="ml-2">Broker VPN: {data.broker_vpn}</div>
            <div className="ml-2">Username: {data.broker_username}</div>
            <div className="ml-2">
              Password: {formatValue('broker_password', data.broker_password)}
            </div>
          </div>
        )}
      </div>
    );
  };

  /** Render built-in agents. */
  const renderBuiltInAgents = (agentIds: string[]) => {
    return (
      <div className="space-y-2">
        {agentIds.map((agentId: string) => {
          const agentInfo = agentMapping[agentId] || { name: agentId };
          return (
            <div key={agentId} className="flex items-center text-gray-700">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-green-500 mr-2"
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
                <span className="font-medium">{agentInfo.name}</span>
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
        <div className="text-gray-700 pl-4 border-l-2 border-gray-200">
          <div className="ml-2">Volume Path: {volumePath}</div>
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
        <div className="text-gray-700 pl-4 border-l-2 border-gray-200">
          <div className="ml-2">Bucket Name: {bucketName}</div>
          <div className="ml-2">Endpoint URL: {endpointUrl}</div>
        </div>
      );
    }

    // Otherwise just display a joined list
    return (
      <div className="text-gray-700">
        {configArray.join(', ')}
      </div>
    );
  };

  /** Render a single group (e.g. "Broker", "LLM Providers"). */
  const renderGroup = (groupName: string, keys: string[]) => {
    // Check if there's at least one non-empty value in the group
    const hasValues = keys.some((key) => !isValueEmpty(data[key]));
    if (!hasValues) return null;
    return (
      <div
        key={groupName}
        className="pb-2 border-b border-gray-200 last:border-0"
      >
        <h4 className="font-medium text-solace-blue">{groupName}</h4>
        <div className="mt-2 space-y-1">
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
              <div key={key} className="text-gray-700">
                {formatDisplayLabel(key)}: {formatValue(key, data[key])}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const cleanDataBeforeSubmit = (data: Record<string, any>) => {
    // if namespace does not end with / add it
    if (data.namespace && !data.namespace.endsWith('/')) {
      data.namespace += '/';
    }
    if (data.container_started){
      //remove container_started from data
      delete data.container_started;
    }
    
    //join provider and model name
    if (data.llm_model_name && data.llm_provider){
      data.llm_model_name = `${data.llm_provider}/${data.llm_model_name}`;
      delete data.llm_provider
    }
  };

  //  Submission Logic
  const submitConfiguration = async (force = false) => {
    cleanDataBeforeSubmit(data);
    try {
      const response = await fetch('api/save_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(force ? { ...data, force: true } : data),
      });

      const result = await response.json();

      // Check if confirmation is needed
      if (response.status === 400 && result.status === 'ask_confirmation') {
        setConfirmationMessage(result.message);
        setShowConfirmation(true);
        return;
      }

      if (!response.ok) {
        throw new Error(
          `HTTP error ${response.status}: ${result.message || 'Unknown error'}`
        );
      }

      if (result.status === 'success') {
        console.log('Configuration sent successfully!');
        setIsSubmitted(true);

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
        throw new Error(result.message || 'Failed to save configuration');
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

  // Confirmation Modal handlers
  const handleConfirm = () => {
    setShowConfirmation(false);
    setIsSubmitting(true);
    submitConfiguration(true);
  };

  const handleCancel = () => {
    setShowConfirmation(false);
    setIsSubmitting(false);
  };

  // Handle form submission
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  //  Rendering
  return (
    <div className="space-y-6">
      {showConfirmation && (
        <ConfirmationModal
          message={confirmationMessage}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}

      {!isSubmitted ? (
        <form onSubmit={onSubmit}>
            {/* Configuration Summary */}
            <div className="bg-white border border-gray-200 rounded-md p-4 space-y-4">
              {Object.entries(CONFIG_GROUPS).map(([groupName, keys]) =>
                renderGroup(groupName, keys)
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
              {isSubmitting ? 'Initializing...' : 'Initialize Project'}
            </Button>
          </div>
        </form>
      ) : (
        <SuccessScreen />
      )}
    </div>
  );
}