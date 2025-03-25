import { useState, useEffect } from 'react';
import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Toggle from '../ui/Toggle';
import Button from '../ui/Button';

type Agent = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  envVars?: {
    key: string;
    label: string;
    placeholder: string;
    type: string;
    defaultValue: string;
    required?: boolean;
    validation?: (value: string) => string | null;
  }[];
};

type BuiltinAgentSetupProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

// Agent configuration
export const builtinAgents: Agent[] = [
  {
    id: 'web_request',
    name: 'Web Request Agent',
    description: 'Can make queries to web to get real-time data',
    enabled: true,
    envVars: [],
  },
  {
    id: 'image_processing',
    name: 'Image Processing Agent',
    description: 'Generate images from text or convert images to text',
    enabled: true,
    envVars: [
      {
        key: 'IMAGE_GEN_ENDPOINT',
        label: 'Image Generation Endpoint',
        placeholder: 'Enter endpoint URL',
        type: 'text',
        defaultValue: '',
        required: true,
      },
      {
        key: 'IMAGE_GEN_API_KEY',
        label: 'Image Generation API Key',
        placeholder: 'Enter API key',
        type: 'password',
        defaultValue: '',
        required: true,
      },
      {
        key: 'IMAGE_GEN_MODEL',
        label: 'Image Generation Model',
        placeholder: 'provider/model-name',
        type: 'text',
        defaultValue: '',
        required: true,
        validation: (value) => {
          if (!value) {
            return 'Image Generation Model is required';
          } 
          if (!value.includes('/')) {
            return 'Model name should follow the format provider/model-name';
          }
          return null;
        }
      },
    ],
  },
];

export default function BuiltinAgentSetup({ data, updateData, onNext, onPrevious }: BuiltinAgentSetupProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [envVars, setEnvVars] = useState<Record<string, string>>({});
  const [agentEnabledState, setAgentEnabledState] = useState<Record<string, boolean>>({});
  const [initialized, setInitialized] = useState(false);

  // Initialize form data
  useEffect(() => {
    if (initialized) return;
    
    const initialAgentState: Record<string, boolean> = {};
    const initialEnvVars: Record<string, string> = {};
    
    // Parse existing env_var data if present
    if (data.env_var && Array.isArray(data.env_var)) {
      data.env_var.forEach((envVar: string) => {
        if (envVar.includes('=')) {
          const [key, value] = envVar.split('=');
          initialEnvVars[key] = value;
        }
      });
    }
    
    // Set default enabled values based on built_in_agent data
    const enabledAgents = data.built_in_agent || [];
    builtinAgents.forEach(agent => {
      // Set default enabled values from existing data or use defaults
      const isAgentEnabled = enabledAgents.includes(agent.id);
      initialAgentState[`enable_${agent.id}`] = isAgentEnabled;
      
      // Initialize env vars
      if (agent.envVars) {
        agent.envVars.forEach(env => {
          // Only set default value if no value exists yet
          if (!initialEnvVars[env.key] && isAgentEnabled) {
            initialEnvVars[env.key] = env.defaultValue;
          }
        });
      }
    });
    
    setEnvVars(initialEnvVars);
    setAgentEnabledState(initialAgentState);
    
    updateData({
      ...initialAgentState,
      built_in_agent: enabledAgents
    });
    
    setInitialized(true);
  }, [data, updateData, initialized]);

  const isAgentEnabled = (agentId: string) => {
    return agentEnabledState[`enable_${agentId}`] !== undefined 
      ? agentEnabledState[`enable_${agentId}`] 
      : !!data[`enable_${agentId}`];
  };

  const handleEnvVarChange = (key: string, value: string) => {
    const newEnvVars = {
      ...envVars,
      [key]: value
    };
    
    setEnvVars(newEnvVars);
    
    const envVarArray = Object.entries(newEnvVars)
      .filter(([_, val]) => val !== '')
      .map(([k, v]) => `${k}=${v}`);
    
    updateData({
      env_var: envVarArray
    });
    
    // Clear error when field is edited
    if (errors[key]) {
      setErrors({
        ...errors,
        [key]: ''
      });
    }
  };

  const handleToggle = (agentId: string, value: boolean) => {
    const newAgentState = {
      ...agentEnabledState,
      [`enable_${agentId}`]: value
    };
    setAgentEnabledState(newAgentState);
    
    updateData({ [`enable_${agentId}`]: value });
    
    // If disabling, clear related env vars and errors
    if (!value) {
      const agent = builtinAgents.find(a => a.id === agentId);
      if (agent?.envVars && agent.envVars.length > 0) {
        const updatedEnvVars = { ...envVars };
        const updatedErrors = { ...errors };
        
        agent.envVars.forEach(env => {
          delete updatedEnvVars[env.key];
          delete updatedErrors[env.key];
        });
        
        setEnvVars(updatedEnvVars);
        setErrors(updatedErrors);
        
        // Update parent data with the new env vars
        const envVarArray = Object.entries(updatedEnvVars)
          .filter(([_, val]) => val !== '')
          .map(([k, v]) => `${k}=${v}`);
        
        updateData({
          env_var: envVarArray
        });
      }
    }
    
    const selectedAgents = builtinAgents
      .filter(agent => {
        if (agent.id === agentId) return value;
        return isAgentEnabled(agent.id);
      })
      .map(agent => agent.id);
    
    updateData({
      built_in_agent: selectedAgents
    });
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    // Validate each enabled agent with required env vars
    builtinAgents.forEach(agent => {
      if (isAgentEnabled(agent.id) && agent.envVars) {
        agent.envVars.forEach(env => {
          // Skip validation for non-required fields that are empty
          if (!env.required && !envVars[env.key]) {
            return;
          }
          
          // Use custom validation function if provided
          if (env.validation) {
            const errorMessage = env.validation(envVars[env.key] || '');
            if (errorMessage) {
              newErrors[env.key] = errorMessage;
              isValid = false;
            }
          } 
          // Otherwise apply basic required field validation
          else if (env.required && !envVars[env.key]) {
            newErrors[env.key] = `${env.label} is required`;
            isValid = false;
          }
        });
      }
    });
    
    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onNext();
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <div className="p-4 bg-solace-light-blue/10 rounded-md mb-4">
          <p className="text-sm text-solace-blue">
            Enable and configure built-in agents to extend your system's capabilities.
          </p>
        </div>
        
        <div className="space-y-4">
          {builtinAgents.map(agent => (
            <div key={agent.id} className="flex flex-col p-4 border border-gray-200 rounded-md">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-medium text-solace-blue">{agent.name}</h3>
                  <p className="text-sm text-gray-500">{agent.description}</p>
                </div>
                <Toggle
                  id={`toggle_${agent.id}`}
                  checked={isAgentEnabled(agent.id)}
                  onChange={(checked) => handleToggle(agent.id, checked)}
                />
              </div>
              
              {/* Show environment variables only if the agent is enabled and has env vars */}
              {isAgentEnabled(agent.id) && agent.envVars && agent.envVars.length > 0 && (
                <div className="space-y-4 mt-4 pt-4 border-t border-gray-200">
                  {agent.envVars.map(env => (
                    <FormField 
                      key={env.key}
                      label={env.label} 
                      htmlFor={env.key}
                      error={errors[env.key]}
                      required={!!env.required}
                    >
                      <Input
                        id={env.key}
                        name={env.key}
                        type={env.type}
                        value={envVars[env.key] || ''}
                        onChange={(e) => handleEnvVarChange(env.key, e.target.value)}
                        placeholder={env.placeholder}
                        required={!!env.required && isAgentEnabled(agent.id)}
                      />
                    </FormField>
                  ))}
                </div>
              )}
            </div>
          ))}
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
        onClick={handleSubmit}
        type="submit"
        >
          Next
      </Button>
      </div>
    </form>
  );
}