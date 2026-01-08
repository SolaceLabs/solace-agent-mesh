import { useState, useEffect, useCallback } from "react";
import StepIndicator from "./StepIndicator";
import AgentBasicInfoStep from "./steps/agent/AgentBasicInfoStep";
import AgentServicesStep from "./steps/agent/AgentServicesStep";
import AgentToolsStep, { Tool } from "./steps/agent/AgentToolsStep";
import AgentFeaturesStep from "./steps/agent/AgentFeaturesStep";
import AgentCardStep from "./steps/agent/AgentCardStep";
import SuccessScreen from "./steps/InitSuccessScreen/SuccessScreen";

export interface Skill {
  id: string;
  name: string;
  description: string;
}

export interface AgentFormData {
  agent_name?: string;
  namespace?: string;
  supports_streaming?: boolean;
  model_type?: string;
  instruction?: string;

  session_service_type?: string;
  session_service_behavior?: string;
  database_url?: string;

  artifact_service_type?: string;
  artifact_service_base_path?: string;
  artifact_service_scope?: string;

  artifact_handling_mode?: string;
  enable_embed_resolution?: boolean;
  enable_artifact_content_instruction?: boolean;

  tools?: Tool[];

  agent_card_description?: string;
  agent_card_default_input_modes?: string[];
  agent_card_default_output_modes?: string[];
  agent_card_skills_str?: string;
  agent_card_skills?: Skill[];

  agent_card_publishing_interval?: number;
  agent_discovery_enabled?: boolean;
  inter_agent_communication_allow_list?: string[];
  inter_agent_communication_deny_list?: string[];
  inter_agent_communication_timeout?: number;

  showSuccessScreen_agent?: boolean;
  [key: string]: unknown;
}

export interface StepProps {
  data: AgentFormData;
  updateData: (data: Partial<AgentFormData>) => void;
  onNext: () => void;
  onPrevious: () => void;
  serverUrl?: string;
  availableTools?: Tool[];
}

export type Step = {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<StepProps>;
};

// eslint-disable-next-line react/prop-types
const AgentReviewSubmitStep: React.FC<StepProps> = ({
  data,
  updateData,
  onPrevious,
  serverUrl = "",
}) => {
  const handleSubmit = async () => {
    console.log("Submitting agent configuration:", data);
    try {
      const processedConfig: Partial<AgentFormData> = JSON.parse(
        JSON.stringify(data)
      );

      if (
        !Array.isArray(processedConfig.agent_card_skills) &&
        processedConfig.agent_card_skills_str
      ) {
        try {
          const parsedSkills = JSON.parse(
            processedConfig.agent_card_skills_str
          );
          if (Array.isArray(parsedSkills)) {
            processedConfig.agent_card_skills = parsedSkills as Skill[];
          } else {
            console.warn(
              "Parsed agent_card_skills_str was not an array, ensuring agent_card_skills is empty array."
            );
            processedConfig.agent_card_skills = [];
          }
        } catch (e) {
          console.warn(
            "Could not parse agent_card_skills_str as JSON, ensuring agent_card_skills is empty array.",
            e
          );
          processedConfig.agent_card_skills = [];
        }
      } else if (!Array.isArray(processedConfig.agent_card_skills)) {
        processedConfig.agent_card_skills = [];
      }
      delete processedConfig.agent_card_skills_str;

      if (Array.isArray(processedConfig.tools)) {
        processedConfig.tools = processedConfig.tools
          .map((toolInstance) => {
            const cleanTool: Partial<Tool> = {};
            if (toolInstance.tool_type)
              cleanTool.tool_type = toolInstance.tool_type;
            if (toolInstance.tool_name)
              cleanTool.tool_name = toolInstance.tool_name;
            if (toolInstance.tool_description)
              cleanTool.tool_description = toolInstance.tool_description;
            if (toolInstance.group_name)
              cleanTool.group_name = toolInstance.group_name;
            if (toolInstance.component_module)
              cleanTool.component_module = toolInstance.component_module;
            if (toolInstance.function_name)
              cleanTool.function_name = toolInstance.function_name;
            if (toolInstance.component_base_path)
              cleanTool.component_base_path = toolInstance.component_base_path;
            if (toolInstance.connection_params)
              cleanTool.connection_params = toolInstance.connection_params;
            if (toolInstance.environment_variables)
              cleanTool.environment_variables =
                toolInstance.environment_variables;
            if (
              toolInstance.required_scopes &&
              toolInstance.required_scopes.length > 0
            )
              cleanTool.required_scopes = toolInstance.required_scopes;
            if (toolInstance.tool_config)
              cleanTool.tool_config = toolInstance.tool_config;

            if (!cleanTool.tool_type) {
              console.error("Tool is missing tool_type:", toolInstance);
              return null;
            }
            return cleanTool as Tool;
          })
          .filter((tool) => tool !== null) as Tool[];
      }

      const apiPayload = {
        agent_name_input: data.agent_name,
        config: processedConfig,
      };

      const response = await fetch(`${serverUrl}/api/save_agent_config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(apiPayload),
      });
      const result = await response.json();

      if (response.ok && result.status === "success") {
        setTimeout(async () => {
          try {
            await fetch(`${serverUrl}/api/shutdown`, { method: "POST" });
          } catch (error) {
            // error expected, shutting the server down
          }
        }, 200);
        if (updateData) updateData({ showSuccessScreen_agent: true });
      } else {
        alert(`Error saving agent: ${result.message || "Unknown error"}`);
      }
    } catch (err) {
      alert(
        `Failed to save agent: ${
          err instanceof Error ? err.message : String(err)
        }`
      );
    }
  };

  return (
    <div>
      <h3 className="text-lg font-semibold mb-2">
        Review and Submit Agent Configuration
      </h3>
      <pre className="bg-gray-100 p-3 rounded overflow-x-auto text-xs max-h-96">
        {JSON.stringify(data, null, 2)}
      </pre>
      <div className="flex justify-end space-x-3 mt-6">
        <button
          onClick={onPrevious}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue-dark"
        >
          Previous
        </button>
        <button
          onClick={handleSubmit}
          className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
        >
          Save Agent & Finish
        </button>
      </div>
    </div>
  );
};

export const addAgentSteps: Step[] = [
  {
    id: "agent-basic",
    title: "Basic Info",
    description: "Name, model, instruction",
    component: AgentBasicInfoStep,
  },
  {
    id: "agent-services",
    title: "Services",
    description: "Session & artifact services",
    component: AgentServicesStep,
  },
  {
    id: "agent-features",
    title: "Features",
    description: "Enable built-in features",
    component: AgentFeaturesStep,
  },
  {
    id: "agent-tools",
    title: "Custom Tools",
    description: "Define custom tools for the agent",
    component: AgentToolsStep,
  },
  {
    id: "agent-card",
    title: "Agent Card & Comms",
    description: "Discovery and communication settings",
    component: AgentCardStep,
  },
  {
    id: "agent-review",
    title: "Review & Submit",
    description: "Review and save configuration",
    component: AgentReviewSubmitStep,
  },
];

export default function AddAgentFlow() {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState<AgentFormData>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);

  const serverUrl = "";

  useEffect(() => {
    Promise.all([
      fetch(`/api/form_schema?type=agent`),
      fetch(`/api/available_tools`),
    ])
      .then(async ([schemaRes, toolsRes]) => {
        if (!schemaRes.ok)
          throw new Error(
            `Failed to fetch agent form schema (status: ${schemaRes.status})`
          );
        if (!toolsRes.ok)
          throw new Error(
            `Failed to fetch available tools (status: ${toolsRes.status})`
          );

        const schemaData = await schemaRes.json();
        const toolsData = await toolsRes.json();

        if (schemaData?.status !== "success" || !schemaData?.defaults) {
          throw new Error(
            schemaData?.message || "Invalid response for agent form schema"
          );
        }
        if (toolsData?.status !== "success") {
          throw new Error(
            toolsData?.message || "Invalid response for available tools"
          );
        }

        setAvailableTools(toolsData);

        const defaults = schemaData.defaults;
        const sanitizedDefaults: AgentFormData = {
          ...defaults,
          agent_card_default_input_modes: (
            defaults.agent_card_default_input_modes_str || "text"
          )
            .split(",")
            .map((s: string) => s.trim())
            .filter(Boolean),
          agent_card_default_output_modes: (
            defaults.agent_card_default_output_modes_str || "text,file"
          )
            .split(",")
            .map((s: string) => s.trim())
            .filter(Boolean),
          inter_agent_communication_allow_list: (
            defaults.inter_agent_communication_allow_list_str || "*"
          )
            .split(",")
            .map((s: string) => s.trim())
            .filter(Boolean),
          inter_agent_communication_deny_list: (
            defaults.inter_agent_communication_deny_list_str || ""
          )
            .split(",")
            .map((s: string) => s.trim())
            .filter(Boolean),
          agent_card_skills_str: defaults.agent_card_skills_str || "[]",
          agent_card_skills: [],
          tools: Array.isArray(defaults.tools) ? defaults.tools : [],
          showSuccessScreen_agent: false,
        };
        delete sanitizedDefaults.agent_card_default_input_modes_str;
        delete sanitizedDefaults.agent_card_default_output_modes_str;
        delete sanitizedDefaults.inter_agent_communication_allow_list_str;
        delete sanitizedDefaults.inter_agent_communication_deny_list_str;

        try {
          const parsedSkills = JSON.parse(
            sanitizedDefaults.agent_card_skills_str || "[]"
          );
          if (Array.isArray(parsedSkills)) {
            sanitizedDefaults.agent_card_skills = parsedSkills.filter(
              (skill: unknown): skill is Skill =>
                typeof skill === "object" &&
                skill !== null &&
                "id" in skill &&
                typeof (skill as Skill).id === "string" &&
                "name" in skill &&
                typeof (skill as Skill).name === "string" &&
                "description" in skill &&
                typeof (skill as Skill).description === "string"
            ) as Skill[];
          }
        } catch (e) {
          console.warn(
            "Could not parse agent_card_skills_str from defaults:",
            e
          );
          sanitizedDefaults.agent_card_skills = [];
        }

        setFormData(sanitizedDefaults);
      })
      .catch((err) => {
        console.error("Error fetching initial data:", err);
        setError(
          `Failed to load agent configuration form: ${
            err instanceof Error ? err.message : String(err)
          }`
        );
      })
      .finally(() => setIsLoading(false));
  }, []);

  const updateFormDataCb = useCallback((newData: Partial<AgentFormData>) => {
    setFormData((prevData) => ({ ...prevData, ...newData }));
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const updatedTools: Tool[] = [];
    updatedTools.push({
      id: "default-artifact-management",
      tool_type: "builtin-group",
      group_name: "artifact_management",
    });
    updateFormDataCb({ tools: updatedTools });
  }, [
    updateFormDataCb,
    isLoading,
  ]);

  const handleNextCb = useCallback(() => {
    if (currentStepIndex < addAgentSteps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }, [currentStepIndex]);

  const handlePreviousCb = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  }, [currentStepIndex]);

  if (isLoading) {
    return (
      <div className="text-center p-10">
        Loading agent configuration form...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center p-10 text-red-600">
        <p>Error: {error}</p>
      </div>
    );
  }

  if (formData.showSuccessScreen_agent) {
    let title = "Agent Configured Successfully!";
    if (formData.agent_name) {
      title = `Agent "${formData.agent_name}" configured successfully!`;
    }
    return (
      <div className="max-w-2xl mx-auto p-6">
        <SuccessScreen
          title={title}
          message="Your new agent configuration has been saved."
          initTab="tutorials"
        />
      </div>
    );
  }

  const CurrentStepComponent = addAgentSteps[currentStepIndex]?.component;

  if (!CurrentStepComponent) {
    return (
      <div className="text-center p-10 text-red-600">
        Error: Configuration step not found for index {currentStepIndex}.
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-4">
      <h2 className="text-2xl font-bold mb-6 text-center text-solace-purple">
        Add New Agent
      </h2>
      {addAgentSteps.length > 1 && (
        <div className="mb-8">
          <StepIndicator
            steps={addAgentSteps}
            currentStepIndex={currentStepIndex}
          />
        </div>
      )}
      <div className="bg-white rounded-lg shadow-xl p-6 min-h-[500px]">
        <CurrentStepComponent
          data={formData}
          updateData={updateFormDataCb}
          onNext={handleNextCb}
          onPrevious={handlePreviousCb}
          serverUrl={serverUrl}
          availableTools={availableTools}
        />
      </div>
    </div>
  );
}
