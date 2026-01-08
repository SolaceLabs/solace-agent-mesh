import { useState, useEffect } from 'react';
import FormField from '../../ui/FormField';
import Input from '../../ui/Input';
import Select from '../../ui/Select';
import ChipInput from '../../ui/ChipInput';
import Button from '../../ui/Button';
import { InfoBox } from '../../ui/InfoBoxes';
import Checkbox from '../../ui/Checkbox';
import { StepComponentProps } from '../../InitializationFlow';

interface OrchestratorData {
  agent_name?: string;
  supports_streaming?: boolean;
  session_service_type?: string;
  orchestrator_database_url?: string;
  session_service_behavior?: string;
  artifact_service_type?: string;
  artifact_service_base_path?: string;
  artifact_service_scope?: string;
  artifact_handling_mode?: string;
  enable_embed_resolution?: boolean;
  enable_artifact_content_instruction?: boolean;
  agent_card_description?: string;
  agent_card_default_input_modes?: string[] | string;
  agent_card_default_output_modes?: string[] | string;
  agent_discovery_enabled?: boolean;
  agent_card_publishing_interval?: number;
  inter_agent_communication_allow_list?: string[] | string;
  inter_agent_communication_deny_list?: string[] | string;
  inter_agent_communication_timeout?: number;
}

const sessionServiceTypeOptions = [
  /* eslint-disable-next-line */
  { value: 'sql', label: 'SQL: Use a SQL database for session data' },
  { value: 'memory', label: 'Memory: Store session data in memory' },
  { value: 'vertex_rag', label: 'Vertex RAG: Use Google Vertex AI for RAG capabilities' },
];

const sessionBehaviorOptions = [
  { value: 'PERSISTENT', label: 'Persistent: Keep session history indefinitely' },
  { value: 'RUN_BASED', label: 'Run-based: Clear session history after each run' },
];

const artifactServiceTypeOptions = [
  { value: 'memory', label: 'Memory: Store artifacts in memory (temporary)' },
  { value: 'filesystem', label: 'Filesystem: Store artifacts on disk' },
  { value: 'gcs', label: 'GCS: Store artifacts in Google Cloud Storage' },
];

const artifactScopeOptions = [
  { value: 'namespace', label: 'Namespace: Share artifacts within the namespace' },
  { value: 'app', label: 'App: Isolate artifacts by app name' },
  { value: 'custom', label: 'Custom: Use a custom scope identifier' },
];

const artifactHandlingModeOptions = [
  { value: 'ignore', label: 'Ignore: Do not include artifacts in messages' },
  { value: 'embed', label: 'Embed: Include base64 data in messages' },
  { value: 'reference', label: 'Reference: Include fetch URI in messages' },
];

export default function OrchestratorSetup({
  data,
  updateData,
  onNext,
  onPrevious,
}: StepComponentProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);

  const stringToArray = (input: string | string[] | undefined, defaultArray: string[]): string[] => {
    if (input === undefined || input === null) {
      return defaultArray;
    }
    if (Array.isArray(input)) {
      return input.map(s => String(s).trim()).filter(s => s.length > 0);
    }
    const trimmedString = String(input).trim();
    if (trimmedString === '') {
      return [];
    }
    return trimmedString.split(',').map(s => s.trim()).filter(s => s.length > 0);
  };
  
  const orchestratorData = data as OrchestratorData;

  const [agentName, setAgentName] = useState(orchestratorData.agent_name || 'OrchestratorAgent');
  const [supportsStreaming, setSupportsStreaming] = useState(orchestratorData.supports_streaming !== false);
  const [sessionServiceType, setSessionServiceType] = useState(orchestratorData.session_service_type || 'sql');
  const [orchestratorDatabaseUrl, setOrchestratorDatabaseUrl] = useState(orchestratorData.orchestrator_database_url || '');
  const [sessionBehavior, setSessionBehavior] = useState(orchestratorData.session_service_behavior || 'PERSISTENT');
  const [artifactServiceType, setArtifactServiceType] = useState(orchestratorData.artifact_service_type || 'filesystem');
  const [artifactBasePath, setArtifactBasePath] = useState(orchestratorData.artifact_service_base_path || '/tmp/samv2');
  const [artifactScope, setArtifactScope] = useState(orchestratorData.artifact_service_scope || 'namespace');
  const [artifactHandlingMode, setArtifactHandlingMode] = useState(orchestratorData.artifact_handling_mode || 'reference');
  const [enableEmbedResolution, setEnableEmbedResolution] = useState(orchestratorData.enable_embed_resolution !== false);
  const [enableArtifactContentInstruction, setEnableArtifactContentInstruction] = useState(orchestratorData.enable_artifact_content_instruction !== false);
  const [agentCardDescription, setAgentCardDescription] = useState(orchestratorData.agent_card_description || 'The Orchestrator component. It manages tasks, and coordinating multi-agent workflows.');
  const [defaultInputModes, setDefaultInputModes] = useState<string[]>(stringToArray(orchestratorData.agent_card_default_input_modes, ['text']));
  const [defaultOutputModes, setDefaultOutputModes] = useState<string[]>(stringToArray(orchestratorData.agent_card_default_output_modes, ['text', 'file']));
  const [agentDiscoveryEnabled, setAgentDiscoveryEnabled] = useState(orchestratorData.agent_discovery_enabled !== false);
  const [cardPublishingInterval, setCardPublishingInterval] = useState(orchestratorData.agent_card_publishing_interval || 10);
  const [allowList, setAllowList] = useState<string[]>(stringToArray(orchestratorData.inter_agent_communication_allow_list, ['*']));
  const [denyList, setDenyList] = useState<string[]>(stringToArray(orchestratorData.inter_agent_communication_deny_list, []));
  const [communicationTimeout, setCommunicationTimeout] = useState(orchestratorData.inter_agent_communication_timeout || 180);

  useEffect(() => {
    if (initialized) return;
    
    if (orchestratorData.agent_name) setAgentName(orchestratorData.agent_name);
    if (orchestratorData.supports_streaming !== undefined) setSupportsStreaming(orchestratorData.supports_streaming);
    if (orchestratorData.session_service_type) setSessionServiceType(orchestratorData.session_service_type);
    /* eslint-disable-next-line */
    // if (orchestratorData.orchestrator_database_url) setOrchestratorDatabaseUrl(orchestratorData.orchestrator_database_url);
    if (orchestratorData.session_service_behavior) setSessionBehavior(orchestratorData.session_service_behavior);
    if (orchestratorData.artifact_service_type) setArtifactServiceType(orchestratorData.artifact_service_type);
    if (orchestratorData.artifact_service_base_path) setArtifactBasePath(orchestratorData.artifact_service_base_path);
    if (orchestratorData.artifact_service_scope) setArtifactScope(orchestratorData.artifact_service_scope);
    if (orchestratorData.artifact_handling_mode) setArtifactHandlingMode(orchestratorData.artifact_handling_mode);
    if (orchestratorData.enable_embed_resolution !== undefined) setEnableEmbedResolution(orchestratorData.enable_embed_resolution);
    if (orchestratorData.enable_artifact_content_instruction !== undefined) setEnableArtifactContentInstruction(orchestratorData.enable_artifact_content_instruction);
    if (orchestratorData.agent_card_description) setAgentCardDescription(orchestratorData.agent_card_description);
    if (orchestratorData.agent_card_default_input_modes !== undefined) setDefaultInputModes(stringToArray(orchestratorData.agent_card_default_input_modes, ['text']));
    if (orchestratorData.agent_card_default_output_modes !== undefined) setDefaultOutputModes(stringToArray(orchestratorData.agent_card_default_output_modes, ['text', 'file']));
    if (orchestratorData.agent_discovery_enabled !== undefined) setAgentDiscoveryEnabled(orchestratorData.agent_discovery_enabled);
    if (orchestratorData.agent_card_publishing_interval) setCardPublishingInterval(orchestratorData.agent_card_publishing_interval);
    if (orchestratorData.inter_agent_communication_allow_list !== undefined) setAllowList(stringToArray(orchestratorData.inter_agent_communication_allow_list, ['*']));
    if (orchestratorData.inter_agent_communication_deny_list !== undefined) setDenyList(stringToArray(orchestratorData.inter_agent_communication_deny_list, []));
    if (orchestratorData.inter_agent_communication_timeout) setCommunicationTimeout(orchestratorData.inter_agent_communication_timeout);
    
    setInitialized(true);
  }, [data, initialized]);

  const handleAgentNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAgentName(e.target.value);
    updateData({ agent_name: e.target.value });
  };

  const handleSupportsStreamingChange = (checked: boolean) => {
    setSupportsStreaming(checked);
    updateData({ supports_streaming: checked });
  };

  const handleSessionServiceTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSessionServiceType(e.target.value);
    updateData({ session_service_type: e.target.value });
  };

  const handleOrchestratorDatabaseUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setOrchestratorDatabaseUrl(e.target.value);
    updateData({ orchestrator_database_url: e.target.value });
  };

  const handleSessionBehaviorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSessionBehavior(e.target.value);
    updateData({ session_service_behavior: e.target.value });
  };

  const handleArtifactServiceTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setArtifactServiceType(e.target.value);
    updateData({ artifact_service_type: e.target.value });
  };

  const handleArtifactBasePathChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setArtifactBasePath(e.target.value);
    updateData({ artifact_service_base_path: e.target.value });
  };

  const handleArtifactScopeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setArtifactScope(e.target.value);
    updateData({ artifact_service_scope: e.target.value });
  };

  const handleArtifactHandlingModeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setArtifactHandlingMode(e.target.value);
    updateData({ artifact_handling_mode: e.target.value });
  };

  const handleEnableEmbedResolutionChange = (checked: boolean) => {
    setEnableEmbedResolution(checked);
    updateData({ enable_embed_resolution: checked });
  };

  const handleEnableArtifactContentInstructionChange = (checked: boolean) => {
    setEnableArtifactContentInstruction(checked);
    updateData({ enable_artifact_content_instruction: checked });
  };

  const handleAgentCardDescriptionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAgentCardDescription(e.target.value);
    updateData({ agent_card_description: e.target.value });
  };

  const handleDefaultInputModesChange = (newValues: string[]) => {
    setDefaultInputModes(newValues);
    updateData({ agent_card_default_input_modes: newValues });
  };

  const handleDefaultOutputModesChange = (newValues: string[]) => {
    setDefaultOutputModes(newValues);
    updateData({ agent_card_default_output_modes: newValues });
  };

  const handleAgentDiscoveryEnabledChange = (checked: boolean) => {
    setAgentDiscoveryEnabled(checked);
    updateData({ agent_discovery_enabled: checked });
  };

  const handleCardPublishingIntervalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCardPublishingInterval(Number(e.target.value));
    updateData({ agent_card_publishing_interval: Number(e.target.value) });
  };

  const handleAllowListChange = (newValues: string[]) => {
    setAllowList(newValues);
    updateData({ inter_agent_communication_allow_list: newValues });
  };

  const handleDenyListChange = (newValues: string[]) => {
    setDenyList(newValues);
    updateData({ inter_agent_communication_deny_list: newValues });
  };

  const handleCommunicationTimeoutChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCommunicationTimeout(Number(e.target.value));
    updateData({ inter_agent_communication_timeout: Number(e.target.value) });
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;
    
    if (!agentName) {
      newErrors.agentName = 'Agent name is required';
      isValid = false;
    } else if (!/^[a-zA-Z0-9_]+$/.test(agentName)) {
      newErrors.agentName = 'Agent name can only contain letters, numbers, and underscores.';
      isValid = false;
    }
    
    if (artifactServiceType === 'filesystem' && !artifactBasePath) {
      newErrors.artifactBasePath = 'Artifact base path is required for filesystem service';
      isValid = false;
    }
    
    if (!cardPublishingInterval || cardPublishingInterval <= 0) {
      newErrors.cardPublishingInterval = 'Publishing interval must be a positive number';
      isValid = false;
    }
    
    if (!communicationTimeout || communicationTimeout <= 0) {
      newErrors.communicationTimeout = 'Communication timeout must be a positive number';
      isValid = false;
    }
    
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
        <InfoBox className="mb-4">
          Configure the main orchestrator for your Solace Agent Mesh system. This will set up the agent that orchestrates communication between components.
        </InfoBox>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="col-span-2">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Basic Configuration</h3>
          </div>
          
          <FormField
            label="Agent Name"
            htmlFor="agent_name"
            error={errors.agentName}
            required
            helpText="The name can only contain letters, numbers, and underscores."
          >
            <Input
              id="agent_name"
              value={agentName}
              onChange={handleAgentNameChange}
              placeholder="OrchestratorAgent"
              required
            />
          </FormField>
          
          <FormField 
            label="Supports Streaming" 
            htmlFor="supports_streaming"
            helpText="Enable streaming support for the agent"
          >
            <Checkbox
              id="supports_streaming"
              checked={supportsStreaming}
              onChange={handleSupportsStreamingChange}
              label="Enable streaming support"
            />
          </FormField>
          
          { /*
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Session Service</h3>
          </div>
          
           <FormField
            label="Session Service Type" 
            htmlFor="session_service_type"
            required
          >
            <Select
              id="session_service_type"
              options={sessionServiceTypeOptions}
              value={sessionServiceType}
              onChange={handleSessionServiceTypeChange}
            />
          </FormField> 

          <FormField
            label="Orchestrator Database URL"
            htmlFor="orchestrator_database_url"
            helpText="Leave blank to create a default SQLite database"
          >
            <Input
              id="orchestrator_database_url"
              value={orchestratorDatabaseUrl}
              onChange={handleOrchestratorDatabaseUrlChange}
              placeholder="e.g., sqlite:///orchestrator.db"
            />
          </FormField>
          
           <FormField
            label="Session Behavior"
            htmlFor="session_behavior"
            required
          >
            <Select
              id="session_behavior"
              options={sessionBehaviorOptions}
              value={sessionBehavior}
              onChange={handleSessionBehaviorChange}
            />
          </FormField>
          */ }
          
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Artifact Service</h3>
          </div>
          
          <FormField 
            label="Artifact Service Type" 
            htmlFor="artifact_service_type"
            required
          >
            <Select
              id="artifact_service_type"
              options={artifactServiceTypeOptions}
              value={artifactServiceType}
              onChange={handleArtifactServiceTypeChange}
            />
          </FormField>
          
          {artifactServiceType === 'filesystem' && (
            <FormField 
              label="Artifact Base Path" 
              htmlFor="artifact_base_path"
              error={errors.artifactBasePath}
              required
            >
              <Input
                id="artifact_base_path"
                value={artifactBasePath}
                onChange={handleArtifactBasePathChange}
                placeholder="/tmp/samv2"
              />
            </FormField>
          )}
          
          <FormField 
            label="Artifact Scope" 
            htmlFor="artifact_scope"
            required
          >
            <Select
              id="artifact_scope"
              options={artifactScopeOptions}
              value={artifactScope}
              onChange={handleArtifactScopeChange}
            />
          </FormField>
          
          <FormField 
            label="Artifact Handling Mode" 
            htmlFor="artifact_handling_mode"
            required
          >
            <Select
              id="artifact_handling_mode"
              options={artifactHandlingModeOptions}
              value={artifactHandlingMode}
              onChange={handleArtifactHandlingModeChange}
            />
          </FormField>
          
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Feature Flags</h3>
          </div>
          
          <FormField 
            label="Enable Embed Resolution" 
            htmlFor="enable_embed_resolution"
          >
            <Checkbox
              id="enable_embed_resolution"
              checked={enableEmbedResolution}
              onChange={handleEnableEmbedResolutionChange}
              label="Enable embed resolution"
            />
          </FormField>
          
          <FormField 
            label="Enable Artifact Content Instruction" 
            htmlFor="enable_artifact_content_instruction"
          >
            <Checkbox
              id="enable_artifact_content_instruction"
              checked={enableArtifactContentInstruction}
              onChange={handleEnableArtifactContentInstructionChange}
              label="Enable artifact content instruction"
            />
          </FormField>
                    
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Agent Card</h3>
          </div>
          
          <div className="col-span-2">
            <FormField 
              label="Agent Card Description" 
              htmlFor="agent_card_description"
              required
            >
              <Input
                id="agent_card_description"
                value={agentCardDescription}
                onChange={handleAgentCardDescriptionChange}
                placeholder="A helpful assistant accessed via a custom endpoint, capable of delegating tasks."
              />
            </FormField>
          </div>
          
          <ChipInput
            id="default_input_modes"
            label="Default Input Modes"
            values={defaultInputModes}
            onChange={handleDefaultInputModesChange}
            helpText="Enter input modes (e.g., text). Press Enter or comma to add."
            placeholder="No input modes added yet."
            inputPlaceholder="e.g., text"
          />
          
          <ChipInput
            id="default_output_modes"
            label="Default Output Modes"
            values={defaultOutputModes}
            onChange={handleDefaultOutputModesChange}
            helpText="Enter output modes (e.g., text, file). Press Enter or comma to add."
            placeholder="No output modes added yet."
            inputPlaceholder="e.g., text, file"
          />
          
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Agent Discovery</h3>
          </div>
          
          <FormField 
            label="Enable Agent Discovery" 
            htmlFor="agent_discovery_enabled"
          >
            <Checkbox
              id="agent_discovery_enabled"
              checked={agentDiscoveryEnabled}
              onChange={handleAgentDiscoveryEnabledChange}
              label="Enable agent discovery"
            />
          </FormField>
          
          <FormField 
            label="Card Publishing Interval" 
            htmlFor="card_publishing_interval"
            error={errors.cardPublishingInterval}
            helpText="Interval in seconds for publishing agent card"
            required
          >
            <Input
              id="card_publishing_interval"
              type="number"
              value={cardPublishingInterval.toString()}
              onChange={handleCardPublishingIntervalChange}
              placeholder="10"
            />
          </FormField>
          
          <div className="col-span-2 mt-4">
            <h3 className="text-lg font-medium text-gray-900 mb-2">Inter-Agent Communication</h3>
          </div>
          
          <ChipInput
            id="allow_list"
            label="Allow List"
            values={allowList}
            onChange={handleAllowListChange}
            helpText="Agent name patterns to allow delegation to (e.g., *, SpecificAgent*). Press Enter or comma to add."
            placeholder="No allow list patterns added."
            inputPlaceholder="e.g., *"
          />
          
          <ChipInput
            id="deny_list"
            label="Deny List"
            values={denyList}
            onChange={handleDenyListChange}
            helpText="Agent name patterns to deny delegation to. Press Enter or comma to add."
            placeholder="No deny list patterns added."
            inputPlaceholder="e.g., RiskyAgent*"
          />
          
          <FormField
            label="Communication Timeout" 
            htmlFor="communication_timeout"
            error={errors.communicationTimeout}
            helpText="Timeout in seconds for inter-agent communication"
            required
          >
            <Input
              id="communication_timeout"
              type="number"
              value={communicationTimeout.toString()}
              onChange={handleCommunicationTimeoutChange}
              placeholder="30"
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
    </form>
  );
}