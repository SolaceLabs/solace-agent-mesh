import { useState, useEffect } from "react";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Checkbox from "../../ui/Checkbox";
import Button from "../../ui/Button";
import { InfoBox } from "../../ui/InfoBoxes";
import { StepComponentProps } from "../../InitializationFlow";

interface PlatformServiceData {
  add_platform_service?: boolean;
  platform_api_host?: string;
  platform_api_port?: number;
  platform_database_url?: string;
  [key: string]: string | number | boolean | undefined;
}

export default function PlatformServiceSetup({
  data,
  updateData,
  onNext,
  onPrevious,
}: StepComponentProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const platformServiceData = data as PlatformServiceData;

  useEffect(() => {
    const defaults: Partial<PlatformServiceData> = {
      add_platform_service: platformServiceData.add_platform_service ?? true,
      platform_api_host: platformServiceData.platform_api_host ?? "127.0.0.1",
      platform_api_port: platformServiceData.platform_api_port ?? 8001,
      platform_database_url:
        platformServiceData.platform_database_url ?? "sqlite:///platform.db",
    };

    const updatesNeeded: Partial<PlatformServiceData> = {};
    for (const key in defaults) {
      if (
        platformServiceData[key] === undefined &&
        defaults[key as keyof typeof defaults] !== undefined
      ) {
        updatesNeeded[key as keyof PlatformServiceData] =
          defaults[key as keyof typeof defaults];
      }
    }
    if (Object.keys(updatesNeeded).length > 0) {
      updateData(updatesNeeded);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type } = e.target;
    if (type === "number") {
      updateData({ [name]: value === "" ? "" : Number(value) });
    } else {
      updateData({ [name]: value });
    }
  };

  const handleCheckboxChange = (
    name: keyof PlatformServiceData,
    checked: boolean
  ) => {
    updateData({ [name]: checked });
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    if (platformServiceData.add_platform_service) {
      if (!platformServiceData.platform_api_host) {
        newErrors.platform_api_host = "Platform API Host is required.";
        isValid = false;
      }
      if (platformServiceData.platform_api_port === undefined) {
        newErrors.platform_api_port = "Platform API Port is required.";
        isValid = false;
      } else if (
        isNaN(Number(platformServiceData.platform_api_port)) ||
        Number(platformServiceData.platform_api_port) <= 0 ||
        Number(platformServiceData.platform_api_port) > 65535
      ) {
        newErrors.platform_api_port =
          "Platform API Port must be a number between 1 and 65535.";
        isValid = false;
      }
      if (!platformServiceData.platform_database_url) {
        newErrors.platform_database_url = "Platform Database URL is required.";
        isValid = false;
      }
    }
    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onNext();
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        <InfoBox className="mb-4">
          Optionally, configure the Platform Service to manage agent
          deployments, connectors, and provide a REST API for platform
          operations.
        </InfoBox>

        <FormField label="" htmlFor="add_platform_service">
          <Checkbox
            id="add_platform_service"
            checked={platformServiceData.add_platform_service || false}
            onChange={(checked) =>
              handleCheckboxChange("add_platform_service", checked)
            }
            label="Add Platform Service"
          />
        </FormField>

        {platformServiceData.add_platform_service && (
          <div className="space-y-4 p-4 border border-gray-200 rounded-md mt-4">
            <h3 className="text-md font-medium text-gray-800 mb-3">
              Platform Service Configuration
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                label="Platform API Host"
                htmlFor="platform_api_host"
                error={errors.platform_api_host}
                required
              >
                <Input
                  id="platform_api_host"
                  name="platform_api_host"
                  value={platformServiceData.platform_api_host || "127.0.0.1"}
                  onChange={handleChange}
                  placeholder="127.0.0.1"
                />
              </FormField>

              <FormField
                label="Platform API Port"
                htmlFor="platform_api_port"
                error={errors.platform_api_port}
                required
              >
                <Input
                  id="platform_api_port"
                  name="platform_api_port"
                  type="number"
                  value={
                    platformServiceData.platform_api_port === undefined
                      ? ""
                      : String(platformServiceData.platform_api_port)
                  }
                  onChange={handleChange}
                  placeholder="8001"
                />
              </FormField>
            </div>

            <FormField
              label="Platform Database URL"
              htmlFor="platform_database_url"
              error={errors.platform_database_url}
              helpText="Database connection string for the platform service (e.g., sqlite:///platform.db or postgresql://user:pass@localhost/db)"
              required
            >
              <Input
                id="platform_database_url"
                name="platform_database_url"
                value={
                  platformServiceData.platform_database_url ||
                  "sqlite:///platform.db"
                }
                onChange={handleChange}
                placeholder="sqlite:///platform.db"
              />
            </FormField>
          </div>
        )}
      </div>

      <div className="mt-8 flex justify-end space-x-4">
        <Button onClick={onPrevious} variant="outline" type="button">
          Previous
        </Button>
        <Button type="submit">Next</Button>
      </div>
    </form>
  );
}
