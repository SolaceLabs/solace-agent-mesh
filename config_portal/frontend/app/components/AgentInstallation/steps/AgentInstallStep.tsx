import React from 'react';
import Button from '../../ui/Button';
import { AgentConfig, InstallStatus } from '../types';
import { InfoBox, StatusBox } from '../../ui/InfoBoxes';
import LoadingSpinner from '../../ui/LoadingSpinner';

type AgentInstallStepProps = {
  selectedAgent: AgentConfig | null;
  agentName: string;
  installStatus: InstallStatus;
  onConfirmInstall: () => Promise<void>;
  onPrevious: () => void;
};

export default function AgentInstallStep({
  selectedAgent,
  agentName,
  installStatus,
  onConfirmInstall,
  onPrevious,
}: Readonly<AgentInstallStepProps>) {
  if (!selectedAgent) {
    return <StatusBox variant="error">Error: No agent selected.</StatusBox>;
  }

  const handleInstallClick = () => {
      if (!installStatus.loading) {
          onConfirmInstall();
      }
  };

  const getButtonContent = () => {
      if (installStatus.loading) {
          return (
              <>
                  <LoadingSpinner className="w-4 h-4 mr-2 inline-block" />
                  Installing...
              </>
          );
      }
      if (installStatus.success === false) {
          return 'Retry Install';
      }
      return 'Confirm & Install';
  };

  return (
    <div className="space-y-6">
      <InfoBox>
        Ready to install agent instance '<strong>{agentName}</strong>' (based on '{selectedAgent.name}')?
        The following command will be executed on the server:
      </InfoBox>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Installation Command (for reference):
        </label>
        <div className="bg-gray-100 p-4 rounded-md font-mono text-sm text-gray-800 border border-gray-300">
          <pre className="whitespace-pre-wrap break-words"><code>{selectedAgent.install_command}</code></pre>
        </div>
         <p className="mt-2 text-xs text-gray-500">
            Ensure your server environment has the necessary prerequisites (like pip, conda, or docker).
        </p>
      </div>

      {installStatus.success === false && (
        <StatusBox variant="error">
            <p className="font-semibold">Installation Failed!</p>
            {installStatus.error && <p className="mb-2">{installStatus.error}</p>}
            {installStatus.output && (
                <details className="text-xs mt-2 bg-red-50 p-2 rounded border border-red-200 max-h-40 overflow-y-auto">
                    <summary className="cursor-pointer font-medium">Show Output Log</summary>
                    <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-red-900">
                        <code>{installStatus.output}</code>
                    </pre>
                </details>
            )}
        </StatusBox>
      )}

      <div className="mt-8 flex justify-between items-center">
        <Button
          onClick={onPrevious}
          variant="outline"
          disabled={installStatus.loading}
        >
          Previous
        </Button>
        <Button
           onClick={handleInstallClick}
           disabled={installStatus.loading || installStatus.success === true}
           variant={installStatus.success === false ? 'danger' : 'primary'}
           className="flex items-center justify-center min-w-[150px]"
        >
           {getButtonContent()}
        </Button>
      </div>
    </div>
  );
}