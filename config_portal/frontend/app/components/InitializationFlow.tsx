import { useState, useEffect } from 'react';
import StepIndicator from './StepIndicator';
import PathSelectionStep from './steps/PathSelectionStep';
import ProjectSetup from './steps/ProjectSetup';
import BrokerSetup from './steps/BrokerSetup';
import AIProviderSetup from './steps/AIProviderSetup';
import BuiltinAgentSetup from './steps/BuiltinAgentSetup';
import FileServiceSetup from './steps/FileServiceSetup';
import CompletionStep from './steps/CompletionStep';
import SuccessScreen from './steps/InitSuccessScreen/SuccessScreen';

// Define step
export type Step = {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<{ data: any; updateData: (data: any) => void; onNext: () => void; onPrevious: () => void }>;
};

// Path selection step
const pathSelectionStep: Step = {
  id: 'path-selection',
  title: 'Setup Path',
  description: 'Choose your setup path',
  component: PathSelectionStep,
};

// Configuration for advanced initialization steps
export const advancedInitSteps: Step[] = [
  {
    id: 'project-setup',
    title: 'Project Structure',
    description: 'Set up your project namespace',
    component: ProjectSetup,
  },
  {
    id: 'broker-setup',
    title: 'Broker Setup',
    description: 'Configure your Solace PubSub+ broker connection',
    component: BrokerSetup,
  },
  {
    id: 'ai-provider-setup',
    title: 'AI Provider',
    description: 'Configure your AI services',
    component: AIProviderSetup,
  },
  {
    id: 'builtin-agent-setup',
    title: 'Built-in Agents',
    description: 'Enable and configure built-in agents',
    component: BuiltinAgentSetup,
  },
  {
    id: 'file-service-setup',
    title: 'File Service',
    description: 'Configure storage for your files',
    component: FileServiceSetup,
  },
  {
    id: 'completion',
    title: 'Review & Submit',
    description: 'Finalize your configuration',
    component: CompletionStep,
  },
];

// Configuration for quick initialization steps
export const quickInitSteps: Step[] = [
  {
    id: 'ai-provider-setup',
    title: 'AI Provider',
    description: 'Configure your AI services',
    component: AIProviderSetup,
  },
  {
    id: 'completion',
    title: 'Review & Submit',
    description: 'Finalize your configuration',
    component: CompletionStep,
  },
];

export default function InitializationFlow() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [setupPath, setSetupPath] = useState<'quick' | 'advanced' | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);
  
  // Determine which steps to show based on the selected path
  const [activeSteps, setActiveSteps] = useState<Step[]>([pathSelectionStep]);
  
  // Fetch default options only after path selection
  useEffect(() => {
    if (setupPath) {
      setIsLoading(true);
      
      fetch(`/api/default_options?path=${setupPath}`)
        .then(response => {
          if (!response.ok) {
            throw new Error('Failed to fetch default options');
          }
          return response.json();
        })
        .then(data => {
          if (data?.default_options) {
            const options = data.default_options;
            preProcessOptions(options);
            setFormData({ ...formData, ...options });
            setIsLoading(false);
          } else {
            throw new Error('Invalid response format');
          }
        })
        .catch(err => {
          console.error('Error fetching default options:', err);
          setError('Failed to connect to server, is the init process still running?');
          setIsLoading(false);
        });
    }
  }, [setupPath]);

  // Pre-process options for certain fields
  const preProcessOptions = (options: Record<string, any>) => {
    if (options.llm_model_name) {
      delete options.llm_model_name;
    }
    if (options.embedding_model_name){
      delete options.embedding_model_name;
    }
  };

  // Update active steps when setup path changes
  useEffect(() => {
    if (setupPath === 'quick') {
      setActiveSteps([pathSelectionStep, ...quickInitSteps]);
    } else if (setupPath === 'advanced') {
      setActiveSteps([pathSelectionStep, ...advancedInitSteps]);
    }
  }, [setupPath]);

  const currentStep = activeSteps[currentStepIndex];
  
  const updateFormData = (newData: Record<string, any>) => {
    // Check if the setupPath is being updated
    if (newData.setupPath && newData.setupPath !== setupPath) {
      setSetupPath(newData.setupPath);
    }
    
    // Check if we should show success screen
    if (newData.showSuccess === true) {
      setShowSuccess(true);
    }
    
    setFormData({ ...formData, ...newData });
  };
  
  const handleNext = () => {
    if (currentStepIndex < activeSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };
  
  const handlePrevious = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  // Loading state
  if (isLoading && currentStepIndex > 0) {
    return (
      <div className="max-w-4xl mx-auto p-6 flex flex-col items-center justify-center min-h-[400px]">
        <h1 className="text-3xl font-bold mb-8 text-solace-blue">Solace Agent Mesh Initialization</h1>
        <div className="bg-white rounded-lg shadow-md p-6 w-full text-center">
          <div className="animate-pulse flex flex-col items-center">
            <div className="h-4 w-1/2 bg-gray-200 rounded mb-4"></div>
            <div className="h-10 w-3/4 bg-gray-200 rounded"></div>
          </div>
          <p className="mt-4">Loading configuration options...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-8 text-center text-solace-blue">Solace Agent Mesh Initialization</h1>
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4" role="alert">
            <p className="font-bold">Error</p>
            <p>{error}</p>
          </div>
          <div className="mt-4 flex justify-center">
            <button 
              onClick={() => window.location.reload()}
              className="bg-solace-blue hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // If we're showing the success screen, render it without any other UI
  if (showSuccess) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <SuccessScreen />
      </div>
    );
  }

  // For all other steps, show the regular flow
  const StepComponent = currentStep.component;
  
  // Only show step indicator after path selection
  const showStepIndicator = currentStepIndex > 0;

  const getStepsForPath = () => {
    if (setupPath === 'quick') return quickInitSteps;
    if (setupPath === 'advanced') return advancedInitSteps;
    return [];
  };
  
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-center text-solace-blue">Solace Agent Mesh Initialization</h1>
      
      {showStepIndicator && (
        <div className="mb-8">
          <StepIndicator
            steps={getStepsForPath()}
            currentStepIndex={currentStepIndex > 0 ? currentStepIndex - 1 : 0}
            onStepClick={(index) => {
              // TODO: Allow clicking on steps to navigate
            }}
          />
        </div>
      )}
      
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-bold mb-2 text-solace-blue">{currentStep.title}</h2>
        <p className="text-gray-600 mb-6">{currentStep.description}</p>
        
        <StepComponent
          data={formData}
          updateData={updateFormData}
          onNext={handleNext}
          onPrevious={handlePrevious}
        />
      </div>
    </div>
  );
}