import { useEffect, useState, ReactNode } from "react";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";
import Button from "../../ui/Button";
import { InfoBox, WarningBox, StatusBox } from "../../ui/InfoBoxes";
import { StepComponentProps } from "../../InitializationFlow";

const brokerOptions = [
  { value: "solace", label: "Existing Solace Pub/Sub+ broker" },
  { value: "container", label: "New local Solace PubSub+ broker container" },
  { value: "dev_mode", label: "Dev mode (simplified setup)" },
];

const containerEngineOptions = [
  { value: "podman", label: "Podman" },
  { value: "docker", label: "Docker" },
];

const ErrorMessage = ({ message }: { message: string }) => {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const parts = message.split(urlRegex);

  return (
    <span>
      {parts.map((part, index) => {
        if (part.match(urlRegex)) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              {part}
            </a>
          );
        }
        return part;
      })}
    </span>
  );
};

export default function BrokerSetup({
  data,
  updateData,
  onNext,
  onPrevious,
}: StepComponentProps) {
  const {
    broker_type,
    broker_url,
    broker_vpn,
    broker_username,
    broker_password,
    container_engine,
    container_started,
  } = data as {
    broker_type?: string;
    broker_url?: string;
    broker_vpn?: string;
    broker_username?: string;
    broker_password?: string;
    container_engine?: string;
    container_started?: boolean;
  };

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isRunningContainer, setIsRunningContainer] = useState(false);
  const [containerStatus, setContainerStatus] = useState<{
    isRunning: boolean;
    success: boolean;
    message: ReactNode;
  }>({
    isRunning: false,
    success: container_started === true,
    message: container_started
      ? "Container already started successfully"
      : "",
  });

  useEffect(() => {
    if (!container_engine && broker_type === "container") {
      updateData({ container_engine: "podman" });
    }
    if (container_engine && broker_type !== "container") {
      updateData({ container_engine: "" });
    }

    if (broker_type !== "dev_mode") {
      updateData({ dev_mode: false });
    } else if (broker_type === "dev_mode") {
      updateData({ dev_mode: true });
    }
  }, [broker_type, container_engine, updateData]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    updateData({ [e.target.name]: e.target.value });
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    if (broker_type === "solace") {
      if (!broker_url) {
        newErrors.broker_url = "Broker URL is required";
        isValid = false;
      }
      if (!broker_vpn) {
        newErrors.broker_vpn = "VPN name is required";
        isValid = false;
      }
      if (!broker_username) {
        newErrors.broker_username = "Username is required";
        isValid = false;
      }
    }

    if (broker_type === "container" && !containerStatus.success) {
      newErrors.container =
        "You must successfully run the container before proceeding";
      isValid = false;
    }

    setErrors(newErrors);
    return isValid;
  };

  const handleRunContainer = async () => {
    setIsRunningContainer(true);
    setContainerStatus({
      isRunning: true,
      success: false,
      message: "Starting container...",
    });

    try {
      const response = await fetch("api/runcontainer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          container_engine: container_engine,
        }),
      });

      const result = await response.json();

      if (result.status === "success") {
        setContainerStatus({
          isRunning: false,
          success: true,
          message: result.message ?? "Container started successfully!",
        });
        updateData({
          container_engine: container_engine,
          container_started: true,
        });
      } else {
        const errorMessage =
          result.message ?? "Failed to start container. Please try again.";
        setContainerStatus({
          isRunning: false,
          success: false,
          message: <ErrorMessage message={errorMessage} />,
        });
        updateData({ container_started: false });
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "An unexpected error occurred";
      setContainerStatus({
        isRunning: false,
        success: false,
        message: <ErrorMessage message={errorMessage} />,
      });
      updateData({ container_started: false });
    } finally {
      setIsRunningContainer(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      if (broker_type === "container") {
        data.broker_url = "ws://localhost:8008";
        data.broker_vpn = "default";
        data.broker_username = "default";
        data.broker_password = "default";
      }
      onNext();
    }
  };

  const showBrokerDetails = broker_type === "solace";
  const showContainerDetails = broker_type === "container";

  const getStatusBoxVariant = () => {
    if (containerStatus.isRunning) return "loading";
    if (containerStatus.success) return "success";
    return "error";
  };

  const renderButtonContent = () => {
    if (isRunningContainer) {
      return (
        <>
          <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            ></circle>
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          Starting Container...
        </>
      );
    }

    if (containerStatus.success) {
      return (
        <>
          <svg
            className="h-4 w-4 mr-2"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          Container Running
        </>
      );
    }

    return (
      <>
        <svg
          className="h-4 w-4 mr-2"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
        Download and Run Container
      </>
    );
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <FormField label="Broker Type" htmlFor="broker_type" required>
          <Select
            id="broker_type"
            name="broker_type"
            options={brokerOptions}
            value={broker_type || ""}
            onChange={handleChange}
            disabled={
              containerStatus.success && data.broker_type === "container"
            }
          />
        </FormField>

        {showBrokerDetails && (
          <div className="space-y-4 p-4 border border-gray-200 rounded-md">
            <InfoBox className="mb-4">
              Connect to an existing Solace PubSub+ broker running locally or in
              the cloud. You will need your broker credentials.
            </InfoBox>

            <FormField
              label="Broker URL"
              htmlFor="broker_url"
              error={errors.broker_url}
              required
            >
              <Input
                id="broker_url"
                name="broker_url"
                value={broker_url || ""}
                onChange={handleChange}
                placeholder="ws://localhost:8008"
              />
            </FormField>

            <FormField
              label="VPN Name"
              htmlFor="broker_vpn"
              error={errors.broker_vpn}
              required
            >
              <Input
                id="broker_vpn"
                name="broker_vpn"
                value={broker_vpn || ""}
                onChange={handleChange}
                placeholder="default"
              />
            </FormField>

            <FormField
              label="Username"
              htmlFor="broker_username"
              error={errors.broker_username}
              required
            >
              <Input
                id="broker_username"
                name="broker_username"
                value={broker_username || ""}
                onChange={handleChange}
                placeholder="default"
              />
            </FormField>

            <FormField
              label="Password"
              htmlFor="broker_password"
              error={errors.broker_password}
            >
              <Input
                id="broker_password"
                name="broker_password"
                type="password"
                value={broker_password || ""}
                onChange={handleChange}
                placeholder="Enter password"
              />
            </FormField>
          </div>
        )}

        {showContainerDetails && (
          <div className="space-y-4 p-4 border border-gray-200 rounded-md">
            <InfoBox className="mb-4">
              This option will download and run a local Solace PubSub+ broker
              container on your machine using Docker or Podman. You need to have
              Docker or Podman installed on your system.
            </InfoBox>

            <FormField
              label="Container Engine"
              htmlFor="container_engine"
              helpText="Select the container engine installed on your system"
              required
            >
              <Select
                id="container_engine"
                name="container_engine"
                options={containerEngineOptions}
                value={container_engine ?? ""}
                onChange={handleChange}
                disabled={containerStatus.isRunning || containerStatus.success}
              />
            </FormField>

            {errors.container && (
              <div className="text-sm text-red-600 mt-1 bg-red-50 p-2 border-l-4 border-red-500">
                {errors.container}
              </div>
            )}

            {containerStatus.message && (
              <StatusBox variant={getStatusBoxVariant()}>
                {containerStatus.message}
              </StatusBox>
            )}

            <div className="relative">
              <div className="flex flex-col">
                <Button
                  onClick={handleRunContainer}
                  disabled={isRunningContainer || containerStatus.success}
                  variant="primary"
                  type="button"
                  className="flex items-center justify-center gap-2"
                >
                  {renderButtonContent()}
                </Button>

                {containerStatus.success && (
                  <div className="mt-2 flex items-center text-sm text-green-600">
                    <svg
                      className="h-4 w-4 mr-1"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    Container is running. You may proceed to the next step.
                  </div>
                )}

                {!containerStatus.success &&
                  !isRunningContainer &&
                  !containerStatus.message && (
                    <div className="mt-2 flex items-center text-sm text-blue-600">
                      <svg
                        className="h-4 w-4 mr-1"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="16" x2="12" y2="12" />
                        <line x1="12" y1="8" x2="12" y2="8" />
                      </svg>
                      You must start the container before proceeding to the next
                      step
                    </div>
                  )}
              </div>
            </div>
          </div>
        )}

        {broker_type === "dev_mode" && (
          <WarningBox>
            <strong>Warning:</strong> Dev mode runs everything in a single
            process and is not recommended for production use.
          </WarningBox>
        )}
      </div>

      <div className="mt-8 flex justify-end space-x-4">
        <Button onClick={onPrevious} variant="outline" type="button">
          Previous
        </Button>

        <Button
          type="submit"
          disabled={
            isRunningContainer ||
            (broker_type === "container" && !containerStatus.success)
          }
          variant={
            broker_type === "container" && !containerStatus.success
              ? "secondary"
              : "primary"
          }
        >
          {broker_type === "container" &&
            !containerStatus.success &&
            !isRunningContainer && (
              <span className="flex items-center">
                <svg
                  className="h-4 w-4 mr-1"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                Run Container First
              </span>
            )}
          {!(
            broker_type === "container" &&
            !containerStatus.success &&
            !isRunningContainer
          ) && "Next"}
        </Button>
      </div>
    </form>
  );
}
