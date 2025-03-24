import { useState, useMemo } from 'react';
import Button from '../ui/Button';
import { builtinAgents } from './BuiltinAgentSetup'; 

type CompletionStepProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

// Words that should always be capitalized
const CAPITALIZED_WORDS = ['llm', 'ai', 'api', 'url', 'vpn'];

export default function CompletionStep({ data, onPrevious }: CompletionStepProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  
  // Create a mapping of agent IDs to their information
  const agentMapping = useMemo(() => {
    const mapping: Record<string, { name: string, envVars?: string[] }> = {};
    builtinAgents.forEach(agent => {
      mapping[agent.id] = { 
        name: agent.name,
        envVars: agent.envVars?.map(env => env.key)
      };
    });
    return mapping;
  }, []);
  
  // Sensitive fields that should be hidden
  const sensitiveFields = [
    'broker_password', 
    'llm_api_key', 
    'embedding_api_key',
  ];
  
  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    
    try {
      // Send the configuration data to the backend
      const response = await fetch('http://localhost:5002/api/save_config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.status === 'success') {
        console.log('Configuration sent successfully!');
        setIsSubmitted(true);
        
        try {
          const shutdownResponse = await fetch('http://localhost:5002/api/shutdown', {
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
      setSubmitError(error instanceof Error ? error.message : 'An unknown error occurred');
      console.error('Error saving configuration:', error);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Format key values for display (hide sensitive ones)
  const formatValue = (key: string, value: any): string => {
    if (sensitiveFields.includes(key) || key.toUpperCase().includes('API_KEY')) {
      return value && value.length > 0 ? '••••••••' : 'Not provided';
    }
    
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    
    return value && value.toString().length > 0 ? value.toString() : 'Not provided';
  };
  
  // Group configuration items by category
  const configGroups = {
    "Project": ["namespace", "config_dir", "module_dir", "env_file", "build_dir"],
    "Broker": ["broker_type", "broker_url", "broker_vpn", "broker_username", "broker_password", "container_engine"],
    "LLM Providers": ["llm_model_name", "llm_endpoint_url", "llm_api_key", "embedding_model_name", "embedding_endpoint_url", "embedding_api_key"],
    "Built-in Agents": ["built_in_agent"],
    "File Service": ["file_service_provider", "file_service_config"],
  };
  
  // Function to format display labels with proper capitalization
  const formatDisplayLabel = (key: string): string => {
    // Split by underscores and capitalize each word appropriately
    return key
      .split('_')
      .map(word => {
        // Check if word should be fully capitalized
        if (CAPITALIZED_WORDS.includes(word.toLowerCase())) {
          return word.toUpperCase();
        }
        // Otherwise capitalize first letter
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(' ');
  };
  
  const getBrokerTypeText = (type: string) => {
    switch (type) {
      case 'solace': return 'Existing Solace Pub/Sub+ broker';
      case 'container': return 'Existing Solace Pub/Sub+ broker';
      case 'dev_mode': return 'Run in dev mode';
      default: return type;
    }
  };
  
  return (
    <div className="space-y-6">
      {!isSubmitted ? (
        <>
          <div className="p-6 bg-solace-light-blue/10 rounded-md mb-4">
            <h3 className="text-xl font-bold text-solace-blue mb-3">Review Your Configuration</h3>
            <p className="text-gray-700 mb-4">
              Review your configuration below. When you're ready, click the "Initialize Project" button to complete the setup.
            </p>
            
            {/* Configuration Summary */}
            <div className="bg-white border border-gray-200 rounded-md p-4 space-y-4">
              {Object.entries(configGroups).map(([groupName, keys]) => {
                // Only show groups that have at least one non-empty value
                const hasValues = keys.some(key => {
                  // For built_in_agent array, check if it has items
                  if (key === 'built_in_agent') {
                    return Array.isArray(data[key]) && data[key].length > 0;
                  }
                  // For file_service_config, check if it has items
                  if (key === 'file_service_config') {
                    return Array.isArray(data[key]) && data[key].length > 0;
                  }
                  return data[key] !== undefined && data[key] !== '';
                });
                
                if (!hasValues) return null;
                
                return (
                  <div key={groupName} className="pb-2 border-b border-gray-200 last:border-0">
                    <h4 className="font-medium text-solace-blue">{groupName}</h4>
                    <div className="mt-2 space-y-1">
                      {keys.map(key => {
                        // Skip empty values
                        if (data[key] === undefined || 
                           (Array.isArray(data[key]) && data[key].length === 0) ||
                           (!Array.isArray(data[key]) && data[key] === '')) {
                          return null;
                        }
                        
                        // handling for broker type
                        if (key === 'broker_type') {
                          return (
                            <div key={key} className="text-gray-700">
                              Type: {getBrokerTypeText(data[key])}
                            </div>
                          );
                        }
                        
                        // Handle built_in_agent
                        if (key === 'built_in_agent' && Array.isArray(data[key])) {
                          return (
                            <div key={key} className="space-y-2">
                              {data[key].map((agentId: string) => {
                                const agentInfo = agentMapping[agentId] || { name: agentId };
                                return (
                                  <div key={agentId} className="flex items-center text-gray-700">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-green-500 mr-2" viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    <div>
                                      <span className="font-medium">{agentInfo.name}</span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          );
                        }
                        
                        // Handle file_service_config
                        if (key === 'file_service_config' && Array.isArray(data[key])) {
                          return (
                            <div key={key} className="text-gray-700">
                              {data[key].map((config: string) => {
                                if (config.startsWith('directory=')) {
                                  return `Volume Path: ${config.split('=')[1]}`;
                                }
                                return config;
                              }).join(', ')}
                            </div>
                          );
                        }
                        
                        // Handle boolean values
                        if (typeof data[key] === 'boolean') {
                          return (
                            <div key={key} className="text-gray-700">
                              {formatDisplayLabel(key)}: {data[key] ? 'Enabled' : 'Disabled'}
                            </div>
                          );
                        }
                        
                        return (
                          <div key={key} className="text-gray-700">
                            {formatDisplayLabel(key)}: {formatValue(key, data[key])}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          
          {submitError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
              <p className="font-medium">Error initializing project</p>
              <p>{submitError}</p>
            </div>
          )}
          
          <div className="mt-8 flex justify-between">
            <Button 
              onClick={onPrevious}
              variant="outline"
            >
              Previous
            </Button>
            
            <Button 
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Initializing...' : 'Initialize Project'}
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="p-6 bg-green-50 rounded-md mb-4 text-center">
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              className="h-16 w-16 mx-auto text-green-500 mb-4" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" 
              />
            </svg>
            
            <h3 className="text-xl font-bold text-green-800 mb-2">
              Solace Agent Mesh Initialized Successfully!
            </h3>
            
            <p className="text-green-700">
              Your configuration has been saved and your project has been set up.
            </p>
          </div>
        
          <div className="p-4 bg-blue-400 text-white rounded-md">
            <h3 className="font-bold mb-2">Next Steps</h3>
            <p className="mb-4">To get started, use the <code className="bg-gray-800 px-1 py-0.5 rounded">solace-agent-mesh add</code> command to add agents and gateways.</p>
            
            <div className="bg-gray-800 text-gray-200 p-3 rounded font-mono text-sm">
              $ solace-agent-mesh add agent my-agent
            </div>
          </div>
        </>
      )}
    </div>
  );
}