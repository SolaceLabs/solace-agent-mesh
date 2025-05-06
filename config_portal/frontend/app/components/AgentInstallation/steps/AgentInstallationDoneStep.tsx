import React from 'react';
import Button from '../../ui/Button';
import { AgentConfig } from '../types';

type AgentInstallationDoneStepProps = {
  selectedAgent: AgentConfig | null;
  onInstallMore: () => void;
  onExit: () => void; 
};

export default function AgentInstallationDoneStep({
    selectedAgent,
    onInstallMore,
    onExit
}: Readonly<AgentInstallationDoneStepProps>) {

    return (
        <div className="text-center space-y-6 p-8">
             <svg className="w-16 h-16 mx-auto text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <h2 className="text-2xl font-semibold text-gray-800">Installation Instructions Provided</h2>
            <p className="text-gray-600">
                You have been shown the instructions to install{' '}
                <span className="font-medium">{selectedAgent?.name ?? 'the selected agent'}</span>.
                Please ensure you follow the steps provided in the previous screen.
            </p>
            <div className="flex justify-center space-x-4 pt-4">
                 <Button onClick={onInstallMore} variant="outline">
                    Install Another Agent
                </Button>
                <Button onClick={onExit} variant="primary">
                    Finish & Exit
                </Button>
            </div>
        </div>
    );
}