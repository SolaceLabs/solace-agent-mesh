import React from "react";
import { StepProps } from "../../AddAgentFlow";
import FormField from "../../ui/FormField";
import Select from "../../ui/Select";
import Checkbox from "../../ui/Checkbox";
import { InfoBox } from "../../ui/InfoBoxes";

const artifactHandlingModeOptions = [
  {
    value: "ignore",
    label: "Ignore (Do not include artifacts in A2A messages)",
  },
  {
    value: "embed",
    label: "Embed (Include base64 artifact data in A2A messages)",
  },
  {
    value: "reference",
    label: "Reference (Include artifact fetch URI in A2A messages)",
  },
];

const AgentFeaturesStep: React.FC<StepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
}) => {
  return (
    <div className="space-y-6">
      <InfoBox>
        Configure various features and behaviors for your agent, such as
        built-in tools and how artifacts are handled.
      </InfoBox>

      <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4">
        Built-in Tools & Features
      </h3>

      <FormField
        label="Artifact Handling Mode"
        htmlFor="artifact_handling_mode"
        helpText="How artifacts created by this agent are represented in A2A messages."
      >
        <Select
          id="artifact_handling_mode"
          name="artifact_handling_mode"
          value={data.artifact_handling_mode || "ignore"}
          onChange={(e) =>
            updateData({ artifact_handling_mode: e.target.value })
          }
          options={artifactHandlingModeOptions}
        />
      </FormField>

      <div className="space-y-3 mt-4">
        <FormField label="" htmlFor="enable_embed_resolution">
          <Checkbox
            id="enable_embed_resolution"
            checked={
              data.enable_embed_resolution === undefined
                ? true
                : !!data.enable_embed_resolution
            }
            onChange={(checked) =>
              updateData({ enable_embed_resolution: checked })
            }
            label="Enable Embed Resolution (for dynamic content like state, math in prompts)"
          />
        </FormField>

        <FormField label="" htmlFor="enable_artifact_content_instruction">
          <Checkbox
            id="enable_artifact_content_instruction"
            checked={
              data.enable_artifact_content_instruction === undefined
                ? true
                : !!data.enable_artifact_content_instruction
            }
            onChange={(checked) =>
              updateData({ enable_artifact_content_instruction: checked })
            }
            label="Enable Artifact Content Instruction (for late-stage artifact content embedding)"
          />
        </FormField>
      </div>

      <div className="flex justify-end space-x-3 mt-8">
        <button
          type="button"
          onClick={onPrevious}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue-dark"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          className="px-4 py-2 text-sm font-medium text-white bg-solace-blue rounded-md shadow-sm hover:bg-solace-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default AgentFeaturesStep;
