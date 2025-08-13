import React from "react";
import { GatewayFormData } from "../../AddGatewayFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";

interface GatewayArtifactServiceStepProps {
  data: GatewayFormData;
  updateData: (newData: Partial<GatewayFormData>) => void;
  onNext: () => void;
  onPrevious: () => void;
}

const ARTIFACT_SERVICE_TYPE_CHOICES = [
  {
    value: "use_default_shared_artifact",
    label: "Use Default Shared Artifact Service",
  },
  { value: "memory", label: "Memory" },
  { value: "filesystem", label: "Filesystem" },
  { value: "gcs", label: "Google Cloud Storage (GCS)" },
  { value: "s3", label: "Amazon S3 Compatible" },
];

const ARTIFACT_SERVICE_SCOPE_CHOICES = [
  { value: "namespace", label: "Namespace" },
  { value: "app", label: "Application (Gateway ID specific)" },
  { value: "custom", label: "Custom (requires specific GDK handling)" },
];

const GatewayArtifactServiceStep: React.FC<GatewayArtifactServiceStepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
}) => {
  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    updateData({ [name]: value });

    if (name === "artifact_service_type") {
      if (value !== "filesystem") {
        updateData({ artifact_service_base_path: undefined });
      }
      if (value !== "s3") {
        updateData({ 
          s3_bucket_name: undefined,
          s3_endpoint_url: undefined,
          s3_region: undefined
        });
      }
    }
  };

  const showCustomArtifactConfig =
    data.artifact_service_type &&
    data.artifact_service_type !== "use_default_shared_artifact";
  const showBasePath = data.artifact_service_type === "filesystem";
  const showS3Config = data.artifact_service_type === "s3";

  let canProceed = true;
  if (showCustomArtifactConfig) {
    if (!data.artifact_service_scope) canProceed = false;
    if (showBasePath && !data.artifact_service_base_path) canProceed = false;
    if (showS3Config) {
      if (!data.s3_bucket_name) canProceed = false;
      if (!data.s3_region) canProceed = false;
    }
  }

  return (
    <div className="space-y-6">
      <FormField
        label="Artifact Service Type"
        htmlFor="artifact_service_type"
        helpText="Determines how gateway artifacts are stored and managed."
      >
        <Select
          id="artifact_service_type"
          name="artifact_service_type"
          value={data.artifact_service_type || ""}
          onChange={handleChange}
          options={ARTIFACT_SERVICE_TYPE_CHOICES}
        />
      </FormField>

      {showCustomArtifactConfig && (
        <>
          <FormField
            label="Artifact Service Scope"
            htmlFor="artifact_service_scope"
            required={showCustomArtifactConfig}
            helpText="Scope for the custom artifact service."
          >
            <Select
              id="artifact_service_scope"
              name="artifact_service_scope"
              value={data.artifact_service_scope || ""}
              onChange={handleChange}
              options={ARTIFACT_SERVICE_SCOPE_CHOICES}
              required={showCustomArtifactConfig}
            />
          </FormField>

          {showBasePath && (
            <FormField
              label="Artifact Service Base Path"
              htmlFor="artifact_service_base_path"
              required={showBasePath}
              helpText="Base directory path if 'Filesystem' type is selected."
            >
              <Input
                id="artifact_service_base_path"
                name="artifact_service_base_path"
                value={data.artifact_service_base_path || ""}
                onChange={handleChange}
                placeholder="/tmp/samv2"
                required={showBasePath}
              />
            </FormField>
          )}

          {showS3Config && (
            <>
              <FormField
                label="S3 Bucket Name"
                htmlFor="s3_bucket_name"
                required={showS3Config}
                helpText="Name of the S3 bucket to store artifacts."
              >
                <Input
                  id="s3_bucket_name"
                  name="s3_bucket_name"
                  value={data.s3_bucket_name || ""}
                  onChange={handleChange}
                  placeholder="my-artifacts-bucket"
                  required={showS3Config}
                />
              </FormField>

              <FormField
                label="S3 Endpoint URL"
                htmlFor="s3_endpoint_url"
                helpText="S3 endpoint URL (leave empty for AWS S3, required for S3-compatible services like MinIO)."
              >
                <Input
                  id="s3_endpoint_url"
                  name="s3_endpoint_url"
                  value={data.s3_endpoint_url || ""}
                  onChange={handleChange}
                  placeholder="https://s3.amazonaws.com or https://minio.example.com"
                />
              </FormField>

              <FormField
                label="S3 Region"
                htmlFor="s3_region"
                required={showS3Config}
                helpText="AWS region or S3-compatible service region."
              >
                <Input
                  id="s3_region"
                  name="s3_region"
                  value={data.s3_region || ""}
                  onChange={handleChange}
                  placeholder="us-east-1"
                  required={showS3Config}
                />
              </FormField>
            </>
          )}
        </>
      )}

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

export default GatewayArtifactServiceStep;
