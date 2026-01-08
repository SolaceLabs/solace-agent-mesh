import React from "react";
import { GatewayFormData } from "../../AddGatewayFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";

interface GatewayBasicInfoStepProps {
  data: GatewayFormData;
  updateData: (newData: Partial<GatewayFormData>) => void;
  onNext: () => void;
}

const GatewayBasicInfoStep: React.FC<GatewayBasicInfoStepProps> = ({
  data,
  updateData,
  onNext,
}) => {
  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >
  ) => {
    updateData({ [e.target.name]: e.target.value });
  };

  const canProceed =
    data.gateway_name_input && data.namespace && data.gateway_id;

  return (
    <div className="space-y-6">
      <FormField
        label="Gateway Name"
        htmlFor="gateway_name_input"
        required
        helpText="A unique name for your gateway. Will be used for directory and class naming (e.g., my_cool_gateway, MyCoolGateway)."
      >
        <Input
          id="gateway_name_input"
          name="gateway_name_input"
          value={data.gateway_name_input || ""}
          onChange={handleChange}
          placeholder="e.g., custom-monitor"
          required
        />
      </FormField>

      <FormField
        label="A2A Namespace"
        htmlFor="namespace"
        required
        helpText="The namespace this gateway will operate under."
      >
        <Input
          id="namespace"
          name="namespace"
          value={data.namespace || ""}
          onChange={handleChange}
          placeholder="e.g., myorg/dev or ${NAMESPACE}"
          required
        />
      </FormField>

      <FormField
        label="Gateway ID"
        htmlFor="gateway_id"
        required
        helpText="A unique identifier for this gateway instance."
      >
        <Input
          id="gateway_id"
          name="gateway_id"
          value={data.gateway_id || ""}
          onChange={handleChange}
          placeholder="e.g., custom-monitor-gateway-gw-01"
          required
        />
      </FormField>

      <div className="flex justify-end mt-8">
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

export default GatewayBasicInfoStep;
