import React from "react";
import { StepProps } from "../../AddAgentFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";
import Checkbox from "../../ui/Checkbox";

const modelTypeOptions = [
  { value: "planning", label: "Planning Model (*planning_model)" },
  { value: "general", label: "General Model (*general_model)" },
  { value: "image_gen", label: "Image Generation Model (*image_gen_model)" },
  { value: "report_gen", label: "Report Generation Model (*report_gen_model)" },
  { value: "multimodal", label: "Multimodal Model (*multimodal_model)" },
  { value: "gemini_pro", label: "Gemini Pro Model (*gemini_pro_model)" },
];

const AgentBasicInfoStep: React.FC<StepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
}) => {
  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value, type } = e.target;
    const val =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : value;
    updateData({ [name]: val });
  };

  const validateAndProceed = () => {
    if (!data.agent_name || data.agent_name.trim() === "") {
      alert("Agent Name is required.");
      return;
    }

    let processedInstruction = data.instruction;

    if (
      typeof processedInstruction === "string" &&
      processedInstruction.includes("__AGENT_NAME__")
    ) {
      const agentName = data.agent_name;
      processedInstruction = processedInstruction.replace(
        /__AGENT_NAME__/g,
        agentName
      );

      updateData({ instruction: processedInstruction });
    }

    onNext();
  };

  const instructionDefault =
    data.instruction ||
    `You are a helpful assistant named ${
      data.agent_name || "NewAgent"
    }, accessed via a custom endpoint.`;

  return (
    <div className="space-y-6">
      <FormField
        label="Agent Name"
        htmlFor="agent_name"
        required
        helpText="Unique name for this agent (will be PascalCase by the system)."
      >
        <Input
          id="agent_name"
          name="agent_name"
          value={data.agent_name || ""}
          onChange={handleChange}
          placeholder="MyNewAgent"
          required
        />
      </FormField>

      <FormField
        label="A2A Namespace"
        htmlFor="namespace"
        helpText="A2A topic namespace (e.g., myorg/dev). Can use ${NAMESPACE} for environment variable."
      >
        <Input
          id="namespace"
          name="namespace"
          value={data.namespace || ""}
          onChange={handleChange}
          placeholder="${NAMESPACE}"
        />
      </FormField>

      <FormField label="Model Type" htmlFor="model_type" required>
        <Select
          id="model_type"
          name="model_type"
          value={data.model_type || "planning"}
          onChange={handleChange}
          options={modelTypeOptions}
        />
      </FormField>

      <FormField
        label="Instruction"
        htmlFor="instruction"
        helpText="System instruction for the agent. Use __AGENT_NAME__ to refer to the agent's name."
      >
        <textarea
          id="instruction"
          name="instruction"
          value={
            data.instruction !== undefined
              ? data.instruction
              : instructionDefault.replace(
                  "__AGENT_NAME__",
                  data.agent_name || "NewAgent"
                )
          }
          onChange={handleChange}
          rows={4}
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm"
          placeholder="You are a helpful assistant..."
        />
      </FormField>

      <FormField label="" htmlFor="supports_streaming">
        <Checkbox
          id="supports_streaming"
          checked={
            data.supports_streaming === undefined
              ? true
              : !!data.supports_streaming
          }
          onChange={(checked) => updateData({ supports_streaming: checked })}
          label="Supports Streaming (host capability for A2A tasks/sendSubscribe)"
        />
      </FormField>

      <div className="flex justify-end space-x-3 mt-8">
        <button
          type="button"
          onClick={onPrevious}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue-dark"
          disabled
        >
          Previous
        </button>
        <button
          type="button"
          onClick={validateAndProceed}
          className="px-4 py-2 text-sm font-medium text-white bg-solace-blue rounded-md shadow-sm hover:bg-solace-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default AgentBasicInfoStep;
