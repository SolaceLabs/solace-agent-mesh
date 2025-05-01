import React from 'react';
import Button from '../../ui/Button';
import { AgentConfig } from '../types';
import { StatusBox } from '../../ui/InfoBoxes';

type AgentConfigureStepProps = {
  selectedAgent: AgentConfig | null;
  agentName: string;
  onInstallMore: () => void;
  onExit: () => void;
  onPrevious: () => void;
};

export default function AgentConfigureStep({
    selectedAgent,
    agentName,
    onInstallMore,
    onExit,
    onPrevious,
}: Readonly<AgentConfigureStepProps>) {
    return (
        <div className="space-y-6 text-center">
             <StatusBox variant='success'>
                Agent instance '<strong>{agentName}</strong>' (based on '{selectedAgent?.name}') was installed successfully!
             </StatusBox>
            <div className="p-6 border rounded-md bg-gray-50 text-gray-700">
                <h3 className="text-lg font-semibold mb-3">Agent Configuration (Placeholder)</h3>
                <p>
                    Configuration options specific to the '<strong>{agentName}</strong>' agent instance will appear here in the future.
                </p>
                <p className="text-sm mt-2">
                    For now, you can finish or choose to install another agent.
                </p>

            </div>
            <div className="flex justify-center space-x-4 pt-4">

                 <Button onClick={onInstallMore} variant="outline">
                    Install Another Agent
                </Button>
                <Button onClick={onExit} variant="primary">
                    Finish
                </Button>
            </div>
        </div>
    );
}