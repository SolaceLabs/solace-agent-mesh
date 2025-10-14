import React from "react";
import { StepProps, AgentFormData } from "../../AddAgentFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";
import { InfoBox } from "../../ui/InfoBoxes";

const USE_DEFAULT_SHARED_SESSION = "use_default_shared_session";
const USE_DEFAULT_SHARED_ARTIFACT = "use_default_shared_artifact";

const sessionServiceTypeOptions = [
  {
    value: USE_DEFAULT_SHARED_SESSION,
    label: "Use Default (from shared_config.yaml)",
  },
  { value: "memory", label: "Memory (In-Process)" },
  { value: "sql", label: "SQL (Relational Database)" },
  { value: "vertex_rag", label: "Vertex RAG (Google Cloud)" },
];

const sessionBehaviorOptions = [
  { value: "PERSISTENT", label: "Persistent (Retains history across runs)" },
  { value: "RUN_BASED", label: "Run-based (Clears history after each run)" },
];

const artifactServiceTypeOptions = [
  {
    value: USE_DEFAULT_SHARED_ARTIFACT,
    label: "Use Default (from shared_config.yaml)",
  },
  { value: "memory", label: "Memory (In-Process, temporary)" },
  { value: "filesystem", label: "Filesystem (Local disk storage)" },
  { value: "gcs", label: "Google Cloud Storage (GCS)" },
];

const artifactScopeOptions = [
  {
    value: "namespace",
    label: "Namespace (Shared by all agents in namespace)",
  },
  { value: "app", label: "App (Isolated to this agent instance)" },
];

const AgentServicesStep: React.FC<StepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
}) => {
  const handleServiceTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = e.target;
    const updates: Partial<AgentFormData> = { [name]: value };

    if (name === "session_service_type") {
      if (value === USE_DEFAULT_SHARED_SESSION) {
        updates.session_service_behavior = undefined;
      } else if (!data.session_service_behavior) {
        updates.session_service_behavior = "PERSISTENT";
      }
      if (value === "sql") {
        updates.database_url = "default_agent_db";
      } else {
        updates.database_url = undefined;
      }
    } else if (name === "artifact_service_type") {
      if (value === USE_DEFAULT_SHARED_ARTIFACT) {
        updates.artifact_service_base_path = undefined;
        updates.artifact_service_scope = undefined;
      } else {
        if (!data.artifact_service_scope)
          updates.artifact_service_scope = "namespace";
        if (value === "filesystem" && !data.artifact_service_base_path) {
          updates.artifact_service_base_path = "/tmp/samv2";
        }
      }
    }
    updateData(updates);
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    updateData({ [e.target.name]: e.target.value });
  };

  const validateAndProceed = () => {
    if (
      data.artifact_service_type === "filesystem" &&
      (!data.artifact_service_base_path ||
        data.artifact_service_base_path.trim() === "")
    ) {
      alert(
        "Artifact Service Base Path is required when type is Filesystem and not using default."
      );
      return;
    }
    onNext();
  };

  const showSessionSpecificConfig =
    data.session_service_type !== USE_DEFAULT_SHARED_SESSION;
  const showArtifactSpecificConfig =
    data.artifact_service_type !== USE_DEFAULT_SHARED_ARTIFACT;

  return (
    <div className="space-y-6">
      <InfoBox>
        Configure how your agent handles artifacts
        (files). You can use default settings from a shared project
        configuration or define them specifically for this agent.
      </InfoBox>

      { /* <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4">
        Session Service
      </h3>

       <FormField
        label="Session Service Configuration"
        htmlFor="session_service_type"
        required
      >
        <Select
          id="session_service_type"
          name="session_service_type"
          value={data.session_service_type || "sql"}
          onChange={handleServiceTypeChange}
          options={sessionServiceTypeOptions}
        />
      </FormField> 
      
      {showSessionSpecificConfig && (
        <FormField
          label="Session Service Behavior"
          htmlFor="session_service_behavior"
          required
        >
          <Select
            id="session_service_behavior"
            name="session_service_behavior"
            value={data.session_service_behavior || "PERSISTENT"}
            onChange={handleChange}
            options={sessionBehaviorOptions}
          />
        </FormField> 
      )}  */ }
      

      <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4 mt-8">
        Artifact Service
      </h3>
      <FormField
        label="Artifact Service Configuration"
        htmlFor="artifact_service_type"
        required
      >
        <Select
          id="artifact_service_type"
          name="artifact_service_type"
          value={data.artifact_service_type || USE_DEFAULT_SHARED_ARTIFACT}
          onChange={handleServiceTypeChange}
          options={artifactServiceTypeOptions}
        />
      </FormField>

      {showArtifactSpecificConfig &&
        data.artifact_service_type === "filesystem" && (
          <FormField
            label="Artifact Service Base Path"
            htmlFor="artifact_service_base_path"
            required
            helpText="Base directory path for filesystem artifact storage."
          >
            <Input
              id="artifact_service_base_path"
              name="artifact_service_base_path"
              value={data.artifact_service_base_path || "/tmp/samv2"}
              onChange={handleChange}
              placeholder="/tmp/samv2"
              required
            />
          </FormField>
        )}

      {showArtifactSpecificConfig && (
        <FormField
          label="Artifact Service Scope"
          htmlFor="artifact_service_scope"
          required
        >
          <Select
            id="artifact_service_scope"
            name="artifact_service_scope"
            value={data.artifact_service_scope || "namespace"}
            onChange={handleChange}
            options={artifactScopeOptions}
          />
        </FormField>
      )}

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
          onClick={validateAndProceed}
          className="px-4 py-2 text-sm font-medium text-white bg-solace-blue rounded-md shadow-sm hover:bg-solace-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default AgentServicesStep;
