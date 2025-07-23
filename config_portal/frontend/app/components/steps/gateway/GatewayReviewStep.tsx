import React from "react";
import { GatewayFormData } from "../../AddGatewayFlow";

interface GatewayReviewStepProps {
  data: GatewayFormData;
  onPrevious: () => void;
  onSubmit: () => void;
  isLoading?: boolean;
}

const GatewayReviewStep: React.FC<GatewayReviewStepProps> = ({
  data,
  onPrevious,
  onSubmit,
  isLoading,
}) => {
  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold text-gray-700 mb-4">
        Review Gateway Configuration
      </h3>

      <div className="bg-white shadow-sm rounded-lg p-6 border border-gray-200">
        <dl className="divide-y divide-gray-200">
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Gateway Name</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              {data.gateway_name_input || "-"}
            </dd>
          </div>
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">A2A Namespace</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              {data.namespace || "-"}
            </dd>
          </div>
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">Gateway ID</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              {data.gateway_id || "-"}
            </dd>
          </div>
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">
              Artifact Service Type
            </dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              {data.artifact_service_type || "-"}
            </dd>
          </div>
          {data.artifact_service_type &&
            data.artifact_service_type !== "use_default_shared_artifact" && (
              <>
                <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
                  <dt className="text-sm font-medium text-gray-500">
                    Artifact Service Scope
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                    {data.artifact_service_scope || "-"}
                  </dd>
                </div>
                {data.artifact_service_type === "filesystem" && (
                  <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
                    <dt className="text-sm font-medium text-gray-500">
                      Artifact Service Base Path
                    </dt>
                    <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                      {data.artifact_service_base_path || "-"}
                    </dd>
                  </div>
                )}
              </>
            )}
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">
              System Purpose
            </dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              <pre className="whitespace-pre-wrap font-sans">
                {data.system_purpose || "-"}
              </pre>
            </dd>
          </div>
          <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
            <dt className="text-sm font-medium text-gray-500">
              Response Format
            </dt>
            <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
              <pre className="whitespace-pre-wrap font-sans">
                {data.response_format || "-"}
              </pre>
            </dd>
          </div>
        </dl>
      </div>

      <div className="flex justify-between mt-8">
        <button
          type="button"
          onClick={onPrevious}
          disabled={isLoading}
          className="px-6 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-opacity-50 disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={isLoading}
          className="px-6 py-2 bg-solace-green text-white rounded-md hover:bg-solace-green-dark focus:outline-none focus:ring-2 focus:ring-solace-green focus:ring-opacity-50 disabled:opacity-50"
        >
          {isLoading ? "Creating Gateway..." : "Create Gateway"}
        </button>
      </div>
    </div>
  );
};

export default GatewayReviewStep;
