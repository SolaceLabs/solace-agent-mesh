/**
 * Connection Required Modal Component
 * 
 * Shows when user tries to select an enterprise source that requires authentication
 * Provides option to navigate to connections panel to authenticate
 */

import React from 'react';
import { AlertCircle, ExternalLink } from 'lucide-react';
import { Button } from '@/lib/components/ui/button';

interface ConnectionRequiredModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceName: string;
  onNavigateToConnections: () => void;
}

export const ConnectionRequiredModal: React.FC<ConnectionRequiredModalProps> = ({
  isOpen,
  onClose,
  sourceName,
  onNavigateToConnections
}) => {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-[100]"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[101] w-full max-w-md">
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl border border-gray-300 dark:border-gray-700 p-6 space-y-4">
          {/* Header */}
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-0.5">
              <AlertCircle className="h-6 w-6 text-amber-500" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-lg">Connection Required</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                You need to connect your {sourceName} account before using it in deep research.
              </p>
            </div>
          </div>

          {/* Content */}
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-900 dark:text-blue-100">
              <strong>How to connect:</strong>
            </p>
            <ol className="list-decimal list-inside text-sm text-blue-800 dark:text-blue-200 mt-2 space-y-1">
              <li>Go to the Connections panel</li>
              <li>Click "Connect" next to {sourceName}</li>
              <li>Authenticate with your account</li>
              <li>Return here to enable the source</li>
            </ol>
          </div>

          {/* Actions */}
          <div className="flex gap-3 justify-end">
            <Button
              variant="outline"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              onClick={onNavigateToConnections}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              Go to Connections
            </Button>
          </div>
        </div>
      </div>
    </>
  );
};