import React from 'react';
import Button from '../../ui/Button';
import { AgentConfig } from '../types';
import { InfoBox } from '../../ui/InfoBoxes';

type AgentSelectionStepProps = {
  availableAgents: AgentConfig[];
  selectedAgent: AgentConfig | null;
  onSelectAgent: (agent: AgentConfig) => void;
  onNext: () => void;
};

export default function AgentSelectionStep({
  availableAgents,
  selectedAgent,
  onSelectAgent,
  onNext,
}: Readonly<AgentSelectionStepProps>) {

  return (
    <div className="space-y-6">
      <InfoBox>Select the agent you would like to install.</InfoBox>
      {availableAgents.length === 0 ? (
        <p className="text-gray-600">No agents available for installation.</p>
      ) : (
        <div className="space-y-4">
          {availableAgents.map((agent) => (
            <div
              key={agent.id}
              className={`
                border rounded-lg p-4 cursor-pointer transition-all flex items-center space-x-4
                ${selectedAgent?.id === agent.id
                  ? 'border-solace-blue bg-solace-light-blue/10 shadow-sm'
                  : 'border-gray-200 hover:border-gray-400 hover:bg-gray-50'}
              `}
              onClick={() => onSelectAgent(agent)}
            >
              <input
                type="radio"
                id={`agent-${agent.id}`}
                name="selectedAgent"
                checked={selectedAgent?.id === agent.id}
                onChange={() => onSelectAgent(agent)}
                className="form-radio h-5 w-5 text-solace-blue focus:ring-solace-blue"
              />
              <label htmlFor={`agent-${agent.id}`} className="flex-grow cursor-pointer">
                <div className="flex justify-between items-center">
                  <span className="font-medium text-gray-800">{agent.name}</span>
                </div>
                <p className="text-sm text-gray-600 mt-1">{agent.description}</p>
              </label>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 flex justify-end">
        <Button onClick={onNext} disabled={!selectedAgent || availableAgents.length === 0}>
          Next
        </Button>
      </div>
    </div>
  );
}
