import { useState, useEffect } from 'react';
import StepIndicator from './StepIndicator';
import ProjectSetup from './steps/ProjectSetup';
import BrokerSetup from './steps/BrokerSetup';
import AIProviderSetup from './steps/AIProviderSetup';
import BuiltinAgentSetup from './steps/BuiltinAgentSetup';
import FileServiceSetup from './steps/FileServiceSetup';
import CompletionStep from './steps/CompletionStep';

// Define step
export type Step = {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<{ data: any; updateData: (data: any) => void; onNext: () => void; onPrevious: () => void }>;
};

// Configuration for initialization steps
export const initSteps: Step[] = [
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
    title: 'Builtin Agents',
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

export default function InitializationFlow() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch default options from the backend when component mounts
  useEffect(() => {
    fetch('/api/default_options')
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch default options');
        }
        return response.json();
      })
      .then(data => {
        if (data && data.default_options) {
          const options = data.default_options;
          
          setFormData(options);
          setIsLoading(false);
        } else {
          throw new Error('Invalid response format');
        }
      })
      .catch(err => {
        console.error('Error fetching default options:', err);
        setError('Failed to load configuration options. Please refresh or try again later.');
        setIsLoading(false);
      });
  }, []);

  const currentStep = initSteps[currentStepIndex];
  
  const updateFormData = (newData: Record<string, any>) => {
    setFormData({ ...formData, ...newData });
  };
  
  const handleNext = () => {
    if (currentStepIndex < initSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };
  
  const handlePrevious = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1);
    }
  };

  // Show loading state
  if (isLoading) {
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

  const StepComponent = currentStep.component;
  
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-center text-solace-blue">Solace Agent Mesh Initialization</h1>
      
      <div className="mb-8">
        <StepIndicator 
          steps={initSteps} 
          currentStepIndex={currentStepIndex} 
          onStepClick={(index) => {
          }} 
        />
      </div>
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