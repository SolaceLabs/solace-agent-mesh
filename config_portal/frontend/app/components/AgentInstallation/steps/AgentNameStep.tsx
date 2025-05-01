import React, { useState, useEffect } from 'react';
import Button from '../../ui/Button';
import FormField from '../../ui/FormField';
import Input from '../../ui/Input';
import { AgentConfig } from '../types';
import { InfoBox } from '../../ui/InfoBoxes';

type AgentNameStepProps = {
  selectedAgent: AgentConfig | null;
  agentName: string;
  updateAgentName: (name: string) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function AgentNameStep({
  selectedAgent,
  agentName,
  updateAgentName,
  onNext,
  onPrevious,
}: Readonly<AgentNameStepProps>) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentName && selectedAgent?.name) {
      updateAgentName(selectedAgent.name);
    }
  }, [agentName, selectedAgent, updateAgentName]);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateAgentName(e.target.value);
    if (error && e.target.value.trim() !== '') {
      setError(null);
    }
  };

  const handleNextClick = () => {
    if (agentName.trim() === '') {
      setError('Agent name cannot be empty.');
      return;
    }
    setError(null);
    onNext();
  };

  return (
    <div className="space-y-6">
        <InfoBox>
            Give your new agent instance a unique name. This helps identify it later.
            The default is '{selectedAgent?.name || 'the agent'}'.
        </InfoBox>
      <FormField
        label="Agent Instance Name"
        htmlFor="agentName"
        error={error ?? undefined}
        required
      >
        <Input
          id="agentName"
          name="agentName"
          value={agentName}
          onChange={handleNameChange}
          placeholder="e.g., My Alpha Analyzer"
          autoFocus
        />
      </FormField>
      <div className="mt-8 flex justify-between">
        <Button onClick={onPrevious} variant="outline">
          Previous
        </Button>
        <Button onClick={handleNextClick} disabled={!agentName.trim()}>
          Next
        </Button>
      </div>
    </div>
  );
}