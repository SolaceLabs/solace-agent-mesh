import React from "react";
import { GatewayFormData, StepProps } from "../../AddGatewayFlow";
import FormField from "../../ui/FormField";

const GatewayResponseCustomizationStep: React.FC<
  StepProps<GatewayFormData>
> = ({ data, updateData, onNext, onPrevious }) => {
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };

  const canProceed = true;

  return (
    <div className="space-y-6">
      <FormField
        label="System Purpose"
        htmlFor="system_purpose"
        helpText="Define the overall purpose and persona of the gateway."
      >
        <textarea
          id="system_purpose"
          name="system_purpose"
          value={data.system_purpose || ""}
          onChange={handleChange}
          rows={6}
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm"
          placeholder="e.g., The system is an AI Chatbot..."
        />
      </FormField>

      <FormField
        label="Response Format"
        htmlFor="response_format"
        helpText="Define how the gateway should format its responses."
      >
        <textarea
          id="response_format"
          name="response_format"
          value={data.response_format || ""}
          onChange={handleChange}
          rows={4}
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm"
          placeholder="e.g., Responses should be clear, concise..."
        />
      </FormField>

      <div className="flex justify-between mt-8">
        <button
          type="button"
          onClick={onPrevious}
          className="px-6 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!canProceed}
          className="px-6 py-2 bg-solace-blue text-white rounded-md hover:bg-solace-purple-dark focus:outline-none focus:ring-2 focus:ring-solace-purple focus:ring-opacity-50 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default GatewayResponseCustomizationStep;
