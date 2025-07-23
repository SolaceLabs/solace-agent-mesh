import { useState, useEffect, useCallback } from "react";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";
import Button from "../../ui/Button";
import ConfirmationModal from "../../ui/ConfirmationModal";
import AutocompleteInput from "../../ui/AutocompleteInput";
import { InfoBox, WarningBox } from "../../ui/InfoBoxes";

import {
  PROVIDER_ENDPOINTS,
  PROVIDER_MODELS,
  fetchModelsFromCustomEndpoint,
  LLM_PROVIDER_OPTIONS,
  formatModelName,
} from "../../../common/providerModels";

type AIProviderSetupProps = {
  data: {
    llm_provider: string;
    llm_endpoint_url: string;
    llm_api_key: string;
    llm_model_name: string;
    [key: string]: string | boolean | number;
  };
  updateData: (data: Record<string, string | boolean | number>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function AIProviderSetup({
  data,
  updateData,
  onNext,
  onPrevious,
}: Readonly<AIProviderSetupProps>) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isTestingConfig, setIsTestingConfig] = useState<boolean>(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [showTestErrorDialog, setShowTestErrorDialog] =
    useState<boolean>(false);
  const [llmModelSuggestions, setLlmModelSuggestions] = useState<string[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState<boolean>(false);
  const [previousProvider, setPreviousProvider] = useState<string | null>(null);

  useEffect(() => {
    console.log(data.setupPath);
    const updates: Record<string, string | boolean | number> = {};

    if (!data.llm_provider) {
      updates.llm_provider = "openai";
    }

    if (Object.keys(updates).length > 0) {
      updateData(updates);
    }
  }, [data, updateData]);

  useEffect(() => {
    if (data.llm_provider) {
      const updates: Record<string, string | boolean | number> = {};

      if (previousProvider !== null && previousProvider !== data.llm_provider) {
        updates.llm_model_name = "";

        if (data.llm_provider !== "openai_compatible") {
          const endpointUrl = PROVIDER_ENDPOINTS[data.llm_provider] || "";
          updates.llm_endpoint_url = endpointUrl;
        } else {
          updates.llm_endpoint_url = "";
        }

        if (Object.keys(updates).length > 0) {
          updateData(updates);
        }
      }

      setPreviousProvider(data.llm_provider);
    }
  }, [data.llm_provider, previousProvider, updateData]);

  useEffect(() => {
    if (data.llm_provider && data.llm_provider !== "openai_compatible") {
      setLlmModelSuggestions(PROVIDER_MODELS[data.llm_provider] || []);
    } else {
      setLlmModelSuggestions([]);
    }
  }, [data.llm_provider]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    updateData({ [e.target.name]: e.target.value });
  };

  const fetchCustomModels = useCallback(async () => {
    if (
      data.llm_provider === "openai_compatible" &&
      data.llm_endpoint_url &&
      data.llm_api_key
    ) {
      setIsLoadingModels(true);
      try {
        const models = await fetchModelsFromCustomEndpoint(
          data.llm_endpoint_url,
          data.llm_api_key
        );
        setLlmModelSuggestions(models);
      } catch (error) {
        console.error("Error fetching models:", error);
      } finally {
        setIsLoadingModels(false);
      }
    }
    return [];
  }, [data.llm_provider, data.llm_endpoint_url, data.llm_api_key]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    if (!data.llm_provider) {
      newErrors.llm_provider = "LLM provider is required";
      isValid = false;
    }

    if (data.llm_provider === "openai_compatible" && !data.llm_endpoint_url) {
      newErrors.llm_endpoint_url = `LLM endpoint is required for OpenAI compatible endpoint}`;
      isValid = false;
    }

    if (!data.llm_model_name) {
      newErrors.llm_model_name = "LLM model name is required";
      isValid = false;
    }
    if (!data.llm_api_key) {
      newErrors.llm_api_key = "LLM API key is required";
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const testLLMConfig = async () => {
    setIsTestingConfig(true);
    setTestError(null);

    try {
      const baseUrl =
        data.llm_provider !== "openai_compatible"
          ? PROVIDER_ENDPOINTS[data.llm_provider] || data.llm_endpoint_url
          : data.llm_endpoint_url;

      const formattedModelName = formatModelName(
        data.llm_model_name,
        data.llm_provider
      );

      const response = await fetch("/api/test_llm_config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: formattedModelName,
          api_key: data.llm_api_key,
          base_url: baseUrl,
        }),
      });

      const result = await response.json();

      if (result.status === "success") {
        setIsTestingConfig(false);
        onNext();
      } else {
        setTestError(result.message ?? "Failed to test LLM configuration");
        setShowTestErrorDialog(true);
        setIsTestingConfig(false);
      }
    } catch (error) {
      setTestError(
        error instanceof Error
          ? `Error: ${error.message}`
          : "An unexpected error occurred while testing the LLM configuration"
      );
      setShowTestErrorDialog(true);
      setIsTestingConfig(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      testLLMConfig();
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <InfoBox className="mb-4">
          Configure your AI service provider for language models. To use a LLM
          provider not in the dropdown choose "OpenAI Compatible Provider" and
          enter your base URL, API key and model name.
        </InfoBox>

        <div className="border-b border-gray-200 pb-4 mb-4">
          <h3 className="text-lg font-medium mb-4 text-gray-700 font-semibold">
            Language Model Configuration
          </h3>

          <FormField
            label="LLM Provider"
            htmlFor="llm_provider"
            error={errors.llm_provider}
            required
          >
            <Select
              id="llm_provider"
              name="llm_provider"
              value={data.llm_provider || ""}
              onChange={handleChange}
              options={LLM_PROVIDER_OPTIONS}
            />
          </FormField>

          {(data.llm_provider === "openai_compatible" ||
            data.llm_provider === "azure") && (
            <FormField
              label="LLM Endpoint URL"
              htmlFor="llm_endpoint_url"
              error={errors.llm_endpoint_url}
              required
            >
              <Input
                id="llm_endpoint_url"
                name="llm_endpoint_url"
                value={data.llm_endpoint_url}
                onChange={handleChange}
                placeholder="https://api.example.com/v1"
              />
            </FormField>
          )}

          <FormField
            label="LLM API Key"
            htmlFor="llm_api_key"
            error={errors.llm_api_key}
            required
          >
            <Input
              id="llm_api_key"
              name="llm_api_key"
              type="password"
              value={data.llm_api_key}
              onChange={handleChange}
              placeholder="Enter your API key"
            />
          </FormField>

          {data.llm_provider === "azure" && (
            <WarningBox className="mb-4">
              <strong>Important:</strong> For Azure, in the "LLM Model Name"
              field, enter your <strong>deployment name</strong> (not the
              underlying model name). Your Azure deployment name is the name you
              assigned when you deployed the model in Azure OpenAI Service. For
              more details, refer to the{" "}
              <a
                href="https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#deploy-a-model"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                Azure documentation
              </a>
              .
            </WarningBox>
          )}
          <FormField
            label="LLM Model Name"
            htmlFor="llm_model_name"
            error={errors.llm_model_name}
            helpText="Select or type a model name"
            required
          >
            <AutocompleteInput
              id="llm_model_name"
              name="llm_model_name"
              value={data.llm_model_name}
              onChange={handleChange}
              placeholder="Select or type a model name"
              suggestions={llmModelSuggestions}
              onFocus={
                data.llm_provider === "openai_compatible"
                  ? fetchCustomModels
                  : undefined
              }
              showLoadingIndicator={isLoadingModels}
            />
          </FormField>
        </div>
      </div>

      <div className="mt-8 flex justify-end space-x-4">
        <Button
          onClick={onPrevious}
          disabled={data.setupPath === "quick"}
          variant="outline"
        >
          Previous
        </Button>
        <Button type="submit">Next</Button>
      </div>

      {isTestingConfig && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full text-center">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Testing LLM Configuration
            </h3>
            <div className="flex justify-center mb-4">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-solace-green"></div>
            </div>
            <p>Please wait while we test your LLM configuration...</p>
          </div>
        </div>
      )}

      {showTestErrorDialog && (
        <ConfirmationModal
          title="Connection Test Failed"
          message={`We couldn't connect to your AI provider: ${testError}
          Please check your API key, model name, and endpoint URL (if applicable).
          Do you want to skip this check and continue anyway?`}
          onConfirm={() => {
            setShowTestErrorDialog(false);
            onNext();
          }}
          onCancel={() => {
            setShowTestErrorDialog(false);
          }}
        />
      )}
    </form>
  );
}
