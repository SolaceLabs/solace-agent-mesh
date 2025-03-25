import React from 'react';
import Button from './Button';

type ConfirmationModalProps = {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmationModal({
  message,
  onConfirm,
  onCancel,
}: ConfirmationModalProps) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Confirmation Required</h3>
        <p className="mb-6 text-gray-700">{message}</p>
        <div className="flex justify-end space-x-3">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm}>
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}