import React, { useState, useEffect, useCallback } from "react";
import StepIndicator from "./StepIndicator";
import SuccessScreen from "./steps/InitSuccessScreen/SuccessScreen";
import GatewayBasicInfoStep from "./steps/gateway/GatewayBasicInfoStep";
import GatewayArtifactServiceStep from "./steps/gateway/GatewayArtifactServiceStep";
import GatewayResponseCustomizationStep from "./steps/gateway/GatewayResponseCustomizationStep";
import GatewayReviewStep from "./steps/gateway/GatewayReviewStep";

export interface StepProps<T> {
  data: T;
  updateData: (newData: Partial<T>) => void;
  onNext: () => void;
  onPrevious: () => void;
  isLoading?: boolean;
  onSubmit?: () => void;
}

export interface Step<T = GatewayFormData> {
  id: string;
  title: string;
  description: string;
  component: React.ComponentType<StepProps<T>>;
}

export interface GatewayFormData {
  gateway_name_input?: string;
  namespace?: string;
  gateway_id?: string;
  artifact_service_type?: string;
  artifact_service_base_path?: string;
  artifact_service_scope?: string;
  system_purpose?: string;
  response_format?: string;
  [key: string]: string | undefined;
}

const gatewaySteps: Step<GatewayFormData>[] = [
  {
    id: "basicInfo",
    title: "Basic Information",
    description: "Enter the core details for your new gateway.",
    component: GatewayBasicInfoStep,
  },
  {
    id: "artifactConfig",
    title: "Artifact Service",
    description: "Configure how artifacts are stored and managed.",
    component: GatewayArtifactServiceStep,
  },
  {
    id: "responseCustomization",
    title: "Response Customization",
    description: "Define the gateway's system purpose and response format.",
    component: GatewayResponseCustomizationStep,
  },
  {
    id: "review",
    title: "Review & Create",
    description: "Review your gateway configuration before creation.",
    component: GatewayReviewStep as React.ComponentType<
      StepProps<GatewayFormData>
    >,
  },
];

const AddGatewayFlow: React.FC = () => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [formData, setFormData] = useState<GatewayFormData>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSuccessScreen_gateway, setShowSuccessScreen_gateway] =
    useState(false);

  const serverUrl = "http://localhost:5002";

  useEffect(() => {
    setIsLoading(true);
    fetch(`${serverUrl}/api/form_schema?type=gateway`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (data.status === "success" && data.defaults) {
          setFormData({
            ...data.defaults,
            gateway_name_input: data.defaults.gateway_name_input || "",
          });
          setError(null);
        } else {
          throw new Error(data.message || "Failed to load gateway defaults.");
        }
      })
      .catch((err) => {
        console.error("Error fetching gateway schema:", err);
        setError(
          err.message || "Could not fetch gateway configuration defaults."
        );
        setFormData({});
      })
      .finally(() => setIsLoading(false));
  }, [serverUrl]);

  const updateFormDataCb = useCallback((newData: Partial<GatewayFormData>) => {
    setFormData((prev) => ({ ...prev, ...newData }));
  }, []);

  const handleNextCb = useCallback(() => {
    if (currentStepIndex < gatewaySteps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    } else {
      handleSubmit();
    }
  }, [currentStepIndex, gatewaySteps.length]);

  const handlePreviousCb = useCallback(() => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  }, [currentStepIndex]);

  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${serverUrl}/api/save_gateway_config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gateway_name_input:
            formData.gateway_name_input ||
            formData.name ||
            "DefaultGatewayName",
          config: formData,
        }),
      });
      const result = await response.json();
      if (response.ok && result.status === "success") {
        setShowSuccessScreen_gateway(true);
        setTimeout(() => {
          fetch(`${serverUrl}/api/shutdown`, { method: "POST" }).catch((err) =>
            console.error("Error shutting down server:", err)
          );
        }, 3000);
      } else {
        throw new Error(
          result.message || "Failed to save gateway configuration."
        );
      }
    } catch (err: unknown) {
      console.error("Error submitting gateway config:", err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred during submission.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (showSuccessScreen_gateway) {
    return (
      <SuccessScreen
        title="Gateway Created!"
        message="Your new gateway configuration has been saved. The CLI will now generate the necessary files."
      />
    );
  }

  if (isLoading && !Object.keys(formData).length) {
    return (
      <div className="text-center p-8">Loading gateway configuration...</div>
    );
  }

  if (error) {
    return <div className="text-center p-8 text-red-600">Error: {error}</div>;
  }

  const CurrentStepComponent = gatewaySteps[currentStepIndex]?.component;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-semibold mb-6 text-center text-gray-700">
        Add New Gateway
      </h2>
      <StepIndicator steps={gatewaySteps} currentStepIndex={currentStepIndex} />

      <div className="mt-6 bg-gray-50 p-6 rounded-lg shadow min-h-[300px]">
        {CurrentStepComponent ? (
          <CurrentStepComponent
            data={formData}
            updateData={updateFormDataCb}
            onNext={handleNextCb}
            onPrevious={handlePreviousCb}
            onSubmit={handleSubmit}
            isLoading={
              isLoading && currentStepIndex === gatewaySteps.length - 1
            }
          />
        ) : (
          <p className="text-center">End of flow or step not found.</p>
        )}
      </div>
      {error && (
        <p className="mt-4 text-sm text-red-500 text-center">{error}</p>
      )}
    </div>
  );
};

export default AddGatewayFlow;
