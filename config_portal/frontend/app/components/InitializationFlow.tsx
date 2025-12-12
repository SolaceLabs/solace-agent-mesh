import { useState, useEffect } from "react";
import StepIndicator from "./StepIndicator";
import PathSelectionStep from "./steps/init/PathSelectionStep";
import ProjectSetup from "./steps/init/ProjectSetup";
import BrokerSetup from "./steps/init/BrokerSetup";
import AIProviderSetup from "./steps/init/AIProviderSetup";
import OrchestratorSetup from "./steps/init/OrchestratorSetup";
import WebUIGatewaySetup from "./steps/init/WebUIGatewaySetup";
import CompletionStep from "./steps/init/CompletionStep";
import SuccessScreen from "./steps/InitSuccessScreen/SuccessScreen";

export interface StepComponentProps {
  data: Partial<Record<string, unknown>>;
  updateData: (newData: Partial<Record<string, unknown>>) => void;
  onNext: () => void;
  onPrevious: () => void;
}

export type Step = {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<StepComponentProps>;
};

const pathSelectionStep: Step = {
  id: "path-selection",
  title: "Setup Path",
  description: "Choose your setup path",
  component: PathSelectionStep,
};

export const advancedInitSteps: Step[] = [
  {
    id: "project-setup",
    title: "Project Structure",
    description: "Set up your project namespace",
    component: ProjectSetup,
  },
  {
    id: "broker-setup",
    title: "Broker Setup",
    description: "Configure your Solace PubSub+ broker connection",
    component: BrokerSetup,
  },
  {
    id: "ai-provider-setup",
    title: "AI Provider",
    description: "Configure your AI services",
    component: AIProviderSetup,
  },
  {
    id: "orchestrator-setup",
    title: "Orchestrator",
    description: "Configure your main orchestrator",
    component: OrchestratorSetup,
  },
  {
    id: "webui-gateway-setup",
    title: "Web UI & Platform Service",
    description: "Configure Web UI Gateway and Platform Service",
    component: WebUIGatewaySetup,
  },
  {
    id: "completion",
    title: "Review & Submit",
    description: "Finalize your configuration",
    component: CompletionStep,
  },
];

export const quickInitSteps: Step[] = [
  {
    id: "ai-provider-setup",
    title: "AI Provider",
    description: "Configure your AI services",
    component: AIProviderSetup,
  },
  {
    id: "completion",
    title: "Review & Submit",
    description: "Finalize your configuration",
    component: CompletionStep,
  },
];

export default function InitializationFlow() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState<Partial<Record<string, unknown>>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [setupPath, setSetupPath] = useState<"quick" | "advanced" | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  const [activeSteps, setActiveSteps] = useState<Step[]>([pathSelectionStep]);

  useEffect(() => {
    if (setupPath) {
      setIsLoading(true);

      fetch(`/api/default_options?path=${setupPath}`)
        .then((response) => {
          if (!response.ok) {
            throw new Error("Failed to fetch default options");
          }
          return response.json();
        })
        .then((data) => {
          if (data?.default_options) {
            const options = data.default_options;
            setFormData((prevData) => ({ ...prevData, ...options }));
            setIsLoading(false);
          } else {
            throw new Error("Invalid response format");
          }
        })
        .catch((err) => {
          console.error("Error fetching default options:", err);
          setError(
            "Failed to connect to server, is the init process still running?"
          );
          setIsLoading(false);
        });
    }
  }, [setupPath]);

  useEffect(() => {
    if (setupPath === "quick") {
      setActiveSteps([pathSelectionStep, ...quickInitSteps]);
    } else if (setupPath === "advanced") {
      setActiveSteps([pathSelectionStep, ...advancedInitSteps]);
    }
  }, [setupPath]);

  const currentStep = activeSteps[currentStepIndex];

  const updateFormData = (newData: Partial<Record<string, unknown>>) => {
    if (newData.setupPath && typeof newData.setupPath === "string" && newData.setupPath !== setupPath) {
      setSetupPath(newData.setupPath as "quick" | "advanced");
    }
    if (newData.showSuccess) {
      setShowSuccess(true);
    }
    setFormData((prevData) => ({ ...prevData, ...newData }));
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

  if (isLoading && currentStepIndex > 0) {
    return (
      <div className="max-w-4xl mx-auto p-6 flex flex-col items-center justify-center min-h-[400px]">
        <h1 className="text-3xl font-bold mb-8 text-solace-blue">
          Solace Agent Mesh Initialization
        </h1>
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

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-8 text-center text-solace-blue">
          Solace Agent Mesh Initialization
        </h1>
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div
            className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4"
            role="alert"
          >
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

  if (showSuccess) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <SuccessScreen
          title="Solace Agent Mesh Initialized Successfully!"
          message="Your project configuration has been saved. You are now ready to start building and running agents."
        />
      </div>
    );
  }

  const StepComponent = currentStep?.component;

  if (!StepComponent) {
    return (
      <div className="text-center p-10 text-red-600">
        Error: Setup step not found.
      </div>
    );
  }

  const showStepIndicator = currentStepIndex > 0;

  const getStepsForPath = () => {
    if (setupPath === "quick") return quickInitSteps;
    if (setupPath === "advanced") return advancedInitSteps;
    return [];
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-center text-solace-blue">
        Solace Agent Mesh Initialization
      </h1>

      {showStepIndicator && (
        <div className="mb-8">
          <StepIndicator
            steps={getStepsForPath()}
            currentStepIndex={currentStepIndex > 0 ? currentStepIndex - 1 : 0}
            onStepClick={() => {
              // TODO: Allow clicking on steps to navigate
            }}
          />
        </div>
      )}

      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-bold mb-2 text-solace-blue">
          {currentStep.title}
        </h2>
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
