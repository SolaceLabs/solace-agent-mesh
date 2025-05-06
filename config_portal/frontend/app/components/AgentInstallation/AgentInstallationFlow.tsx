import React, { useState, useEffect, useCallback } from 'react';
import StepIndicator from '../StepIndicator';
import AgentSelectionStep from './steps/AgentSelectionStep';
import AgentNameStep from './steps/AgentNameStep';
import AgentInstallStep from './steps/AgentInstallStep';
import AgentConfigureStep from './steps/AgentConfigureStep';
import { AgentConfig, Step, InstallStatus } from './types';
import { StatusBox } from '../ui/InfoBoxes';

const agentInstallationSteps: Step[] = [
  {
    id: 'select-agent',
    title: 'Select Type', 
    description: 'Choose the type of agent to install',
    component: AgentSelectionStep,
  },
  {
    id: 'name-agent',
    title: 'Name Agent',
    description: 'Assign a unique name to this agent instance',
    component: AgentNameStep,
  },
  {
    id: 'install-agent',
    title: 'Install',
    description: 'Confirm and execute the installation command',
    component: AgentInstallStep,
  },
  {
    id: 'configure-agent',
    title: 'Configure',
    description: 'Agent installed - configure settings (placeholder)',
    component: AgentConfigureStep,
  },
];

// Initial install status
const initialInstallStatus: InstallStatus = {
    loading: false,
    success: null,
    error: null,
    output: null,
};

export default function AgentInstallationFlow() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [availableAgents, setAvailableAgents] = useState<AgentConfig[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentConfig | null>(null);
  const [agentName, setAgentName] = useState<string>(''); 
  const [installStatus, setInstallStatus] = useState<InstallStatus>(initialInstallStatus);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Fetch agent configurations
  useEffect(() => {
    setIsLoadingConfig(true);
    setFetchError(null);
    fetch('/wizard_api/agents/config')
      .then(response => {
        if (!response.ok) throw new Error(`Failed to fetch agent configurations (Status: ${response.status})`);
        return response.json();
      })
      .then(data => {
        if (data?.agents && Array.isArray(data.agents)) setAvailableAgents(data.agents);
        else throw new Error('Invalid response format from server');
        setIsLoadingConfig(false);
      })
      .catch(err => {
        console.error('Error fetching agent configurations:', err);
        setFetchError(err.message || 'Could not connect to the server to get agent list.');
        setIsLoadingConfig(false);
      });
  }, []);

  // Handler for selecting an agent 
  const handleSelectAgent = useCallback((agent: AgentConfig) => {
    setSelectedAgent(agent);
    setAgentName(agent.name);
    // Reset install status if selecting a new agent after a previous attempt
    setInstallStatus(initialInstallStatus);
  }, []); 

  const handleUpdateAgentName = useCallback((name: string) => {
    setAgentName(name);
  }, []);

  const handleInstallAgent = useCallback(async () => {
    if (!selectedAgent) {
      console.error("Install attempted without selected agent.");
      setInstallStatus({ loading: false, success: false, error: "No agent selected.", output: null });
      return;
    }

    setInstallStatus({ loading: true, success: null, error: null, output: null });

    try {
      const response = await fetch('/wizard_api/agents/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_id: selectedAgent.id,
          agent_name: agentName,
        }),
      });

      const result = await response.json();

      if (response.ok && result.status === 'success') {
        setInstallStatus({
            loading: false,
            success: true,
            error: null,
            output: result.output ?? null
        });

        setCurrentStepIndex(prevIndex => {
            const nextIndex = prevIndex + 1;
            return nextIndex < agentInstallationSteps.length ? nextIndex : prevIndex;
        });

      } else {
        setInstallStatus({
          loading: false,
          success: false,
          error: result.message || `Installation failed (HTTP ${response.status})`,
          output: result.output ?? null,
        });
      }
    } catch (error) {
      console.error('Installation fetch error:', error);
      setInstallStatus({
        loading: false,
        success: false,
        error: error instanceof Error ? error.message : 'Network error during installation.',
        output: null,
      });
    }
  }, [selectedAgent, agentName]); 

  const handleNext = () => {
    if (currentStepIndex < agentInstallationSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStepIndex > 0) {
      const targetIndex = currentStepIndex - 1;
      if (currentStepIndex <= 2) {
          setInstallStatus(initialInstallStatus);
      }
      setCurrentStepIndex(targetIndex);
    }
  };

  // Reset flow to start over
  const handleInstallMore = () => {
    setSelectedAgent(null);
    setAgentName('');
    setInstallStatus(initialInstallStatus);
    setCurrentStepIndex(0);
  };

  // TODO: Implement proper exit behavior (e.g., navigate away)
  const handleExit = () => {
    console.log("Exiting agent installation flow.");
    alert("Exiting agent installation flow.");
  };

  const currentStep = agentInstallationSteps[currentStepIndex];
  const StepComponent = currentStep.component;

  // --- Loading and Error states for initial config fetch ---
   if (isLoadingConfig) {
    return (
      <div className="max-w-2xl mx-auto p-6 text-center">
         <h1 className="text-2xl font-bold mb-6 text-center text-solace-blue">Install New Agent</h1>
         <StatusBox variant="loading">Loading available agent types...</StatusBox>
      </div>
    );
  }
  if (fetchError) {
     return (
      <div className="max-w-2xl mx-auto p-6">
         <h1 className="text-2xl font-bold mb-6 text-center text-solace-blue">Install New Agent</h1>
         <StatusBox variant="error">
            <p className="font-semibold">Failed to load agent types:</p>
            <p>{fetchError}</p>
             {/* Simple retry by reload */}
            <button onClick={() => window.location.reload()} className="mt-4 bg-red-100 text-red-700 border border-red-300 px-3 py-1 rounded text-sm hover:bg-red-200">
              Retry
            </button>
         </StatusBox>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6 text-center text-solace-blue">Install New Agent</h1>

      <div className="mb-8">
          <StepIndicator
          //TODO: Fix steps type error
            steps={agentInstallationSteps}
            currentStepIndex={currentStepIndex}
            onStepClick={(index) => {
               if (index < currentStepIndex && !installStatus.loading) {
                   handlePrevious();
               }
            }}
          />
        </div>

      <div className="bg-white rounded-lg shadow-md p-6 mb-6 min-h-[350px]">
         <h2 className="text-xl font-bold mb-2 text-solace-blue">{currentStep.title}</h2>
         <p className="text-gray-600 mb-6">{currentStep.description}</p>

        <StepComponent
          // Pass ALL potentially needed props to every step
          availableAgents={availableAgents}
          selectedAgent={selectedAgent}
          onSelectAgent={handleSelectAgent}

          agentName={agentName}
          updateAgentName={handleUpdateAgentName}

          installStatus={installStatus}
          onConfirmInstall={handleInstallAgent}

          onNext={handleNext}
          onPrevious={handlePrevious}
          onInstallMore={handleInstallMore}
          onExit={handleExit}
        />
      </div>
    </div>
  );
}