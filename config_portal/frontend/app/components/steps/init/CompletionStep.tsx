import { useState } from "react";
import Button from "../../ui/Button";
import {
  PROVIDER_PREFIX_MAP,
  formatModelName,
} from "../../../common/providerModels";
import { StepComponentProps } from "../../InitializationFlow";

const CAPITALIZED_WORDS = ["llm", "ai", "api", "url", "vpn"];

const SENSITIVE_FIELDS = [
  "broker_password",
  "llm_api_key",
  "webui_session_secret_key",
];

const CONFIG_GROUPS: Record<string, string[]> = {
  Project: ["namespace"],
  Broker: [
    "dev_mode",
    "broker_type",
    "broker_url",
    "broker_vpn",
    "broker_username",
    "broker_password",
  ],
  "AI Provider": ["llm_model_name", "llm_endpoint_url", "llm_api_key"],
  Orchestrator: [
    "agent_name",
    "supports_streaming",
    "session_service_type",
    "session_service_behavior",
    "artifact_service_type",
    "artifact_service_base_path",
    "artifact_service_scope",
    "artifact_handling_mode",
    "enable_embed_resolution",
    "enable_artifact_content_instruction",
    "agent_card_description",
    "agent_card_default_input_modes",
    "agent_card_default_output_modes",
    "agent_discovery_enabled",
    "agent_card_publishing_interval",
    "inter_agent_communication_allow_list",
    "inter_agent_communication_deny_list",
    "inter_agent_communication_timeout",
  ],
  "Web UI & Platform Service": [
    "add_webui_gateway",
    "webui_frontend_welcome_message",
    "webui_frontend_bot_name",
    "webui_frontend_collect_feedback",
    "webui_session_secret_key",
    "webui_fastapi_host",
    "webui_fastapi_port",
    "webui_enable_embed_resolution",
    "platform_api_host",
    "platform_api_port",
  ],
};

export default function CompletionStep({
  data,
  updateData,
  onPrevious,
}: StepComponentProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const isValueEmpty = (value: unknown) => {
    return (
      value === undefined ||
      value === "" ||
      (Array.isArray(value) && value.length === 0)
    );
  };

  const formatDisplayLabel = (key: string): string => {
    return key
      .split("_")
      .map((word) => {
        if (CAPITALIZED_WORDS.includes(word.toLowerCase())) {
          return word.toUpperCase();
        }
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(" ");
  };

  const formatValue = (key: string, value: unknown): string => {
    if (
      SENSITIVE_FIELDS.includes(key) ||
      key.toUpperCase().includes("API_KEY")
    ) {
      return value ? "••••••••" : "Not provided";
    }
    if (typeof value === "boolean") {
      return value ? "Yes" : "No";
    }
    if (Array.isArray(value)) {
      return value.join(", ");
    }
    return value ? String(value) : "Not provided";
  };

  const getBrokerTypeText = (type: string) => {
    switch (type) {
      case "solace":
        return "Existing Solace Pub/Sub+ broker";
      case "container":
        return "New local Solace PubSub+ broker container (podman/docker)";
      case "dev_mode":
        return "Run in 'dev mode' - all in one process (not recommended for production)";
      default:
        return type;
    }
  };

  const renderBrokerDetails = () => {
    const type = data.broker_type as string;
    if (data.dev_mode) {
      return (
        <div>
          <div className="mb-1">
            <span className="text-gray-600">Type:</span>
            <span className="font-medium text-gray-900 ml-2">
              {getBrokerTypeText("dev_mode")}
            </span>
          </div>
        </div>
      );
    }

    return (
      <div>
        <div className="mb-1">
          <span className="text-gray-600">Type:</span>
          <span className="font-medium text-gray-900 ml-2">
            {getBrokerTypeText(type)}
          </span>
        </div>

        {type === "container" && (
          <div className="pl-4 border-l-2 border-gray-300 mb-2">
            <div className="flex mb-1">
              <span className="text-gray-600">Container Engine:</span>
              <span className="font-medium text-gray-900 ml-2">
                {String(data.container_engine) ?? "Docker"}
              </span>
            </div>
          </div>
        )}

        {(type === "solace" || type === "container") && (
          <div className="pl-4 border-l-2 border-gray-300">
            <div className="flex mb-1">
              <span className="text-gray-600">Broker URL:</span>
              <span className="font-medium text-gray-900 ml-2">
                {String(data.broker_url)}
              </span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Broker VPN:</span>
              <span className="font-medium text-gray-900 ml-2">
                {String(data.broker_vpn)}
              </span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Username:</span>
              <span className="font-medium text-gray-900 ml-2">
                {String(data.broker_username)}
              </span>
            </div>
            <div className="flex mb-1">
              <span className="text-gray-600">Password:</span>
              <span className="font-medium text-gray-900 ml-2">
                {formatValue("broker_password", data.broker_password)}
              </span>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderGroup = (groupName: string, keys: string[]) => {
    const hasValues = keys.some((key) => !isValueEmpty(data[key]));

    if (!hasValues) return null;

    return (
      <div
        key={groupName}
        className="pb-4 mb-4 border-b border-gray-300 last:border-0 last:mb-0 last:pb-0"
      >
        <h4 className="font-semibold text-solace-blue mb-3">{groupName}</h4>
        <div className="space-y-3">
          {keys.map((key) => {
            if (isValueEmpty(data[key])) return null;

            if (key === "dev_mode")
              return <div key={key}>{renderBrokerDetails()}</div>;

            return (
              <div key={key} className="flex mb-1">
                <span className="text-gray-600">
                  {formatDisplayLabel(key)}:
                </span>
                <span className="font-medium text-gray-900 ml-2">
                  {formatValue(key, data[key])}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const cleanDataBeforeSubmit = (dataToClean: Record<string, unknown>) => {
    const cleanedData = { ...dataToClean };
    if (cleanedData.namespace && !String(cleanedData.namespace).endsWith("/")) {
      cleanedData.namespace += "/";
    }
    if (cleanedData.container_started) {
      delete cleanedData.container_started;
    }
    if (cleanedData.llm_provider) {
      cleanedData.llm_provider = PROVIDER_PREFIX_MAP[cleanedData.llm_provider as keyof typeof PROVIDER_PREFIX_MAP];
    }

    if (cleanedData.llm_model_name && cleanedData.llm_provider) {
      cleanedData.llm_model_name = formatModelName(
        String(cleanedData.llm_model_name),
        String(cleanedData.llm_provider)
      );
      delete cleanedData.llm_provider;
    }
    if (data.broker_type === "container") {
      
      data.broker_type = "solace";
    }
    return cleanedData;
  };

  const submitConfiguration = async (force = true) => {
    const cleanedData = cleanDataBeforeSubmit(data);
    console.log("Submitting configuration:", cleanedData);
    try {
      const response = await fetch("api/save_config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(force ? { ...cleanedData, force: true } : cleanedData),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          `HTTP error ${response.status}: ${result.message ?? "Unknown error"}`
        );
      }

      if (result.status === "success") {
        console.log("Configuration sent successfully!");

        updateData({ showSuccess: true });

        try {
          const shutdownResponse = await fetch("api/shutdown", {
            method: "POST",
          });
          if (!shutdownResponse.ok) {
            console.warn("Shutdown request failed:", shutdownResponse.status);
          } else {
            console.log("Shutdown request sent successfully");
          }
        } catch (shutdownError) {
          console.error("Error sending shutdown request:", shutdownError);
        }
      } else {
        throw new Error(result.message ?? "Failed to save configuration");
      }
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "An unknown error occurred"
      );
      console.error("Error saving configuration:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    await submitConfiguration();
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit}>
        <div className="bg-gray-100 border border-gray-300 rounded-md p-5 space-y-4">
          {(data.setupPath === "quick")
            ? renderGroup("AI Provider", CONFIG_GROUPS["AI Provider"])
            : Object.entries(CONFIG_GROUPS).map(([groupName, keys]) =>
                renderGroup(groupName, keys)
              )}
        </div>
        {submitError && (
          <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
            <p className="font-medium">Error initializing project</p>
            <p>{submitError}</p>
          </div>
        )}
        <div className="mt-8 flex justify-end space-x-4">
          <Button onClick={onPrevious} variant="outline" type="button">
            Previous
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <div className="flex items-center space-x-2">
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                <span>Initializing...</span>
              </div>
            ) : (
              "Initialize Project"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
