import React, { useState } from "react";

const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "default";
    className?: string;
  }
> = ({ variant = "default", className, children, ...props }) => {
  const baseStyle =
    "px-4 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-800 disabled:opacity-50 disabled:pointer-events-none";
  const primaryStyle =
    "bg-green-600 hover:bg-green-700 text-white dark:bg-green-500 dark:hover:bg-green-600";
  const defaultStyle =
    "bg-gray-200 hover:bg-gray-300 text-gray-800 dark:bg-gray-600 dark:hover:bg-gray-500 dark:text-gray-100";

  let styleToApply = defaultStyle;
  if (variant === "primary") {
    styleToApply = primaryStyle;
  }

  return (
    <button
      {...props}
      className={`${baseStyle} ${styleToApply} ${className || ""}`.trim()}
    >
      {children}
    </button>
  );
};

const Input: React.FC<
  React.InputHTMLAttributes<HTMLInputElement> & { className?: string }
> = ({ className, ...props }) => (
  <input
    {...props}
    className={`flex h-10 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-800 disabled:cursor-not-allowed disabled:opacity-50 ${
      className || ""
    }`}
  />
);

const Label: React.FC<
  React.LabelHTMLAttributes<HTMLLabelElement> & { className?: string }
> = ({ className, children, ...props }) => (
  <label
    {...props}
    className={`block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 ${
      className || ""
    }`}
  >
    {children}
  </label>
);

interface InstallPluginModalProps {
  pluginName: string;
  isOpen: boolean;
  onClose: () => void;
  onInstall: (componentName: string) => Promise<void>;
  isLoading?: boolean;
}

const InstallPluginModal: React.FC<InstallPluginModalProps> = ({
  pluginName,
  isOpen,
  onClose,
  onInstall,
  isLoading = false,
}) => {
  const [componentName, setComponentName] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) {
    return null;
  }

  const handleClose = () => {
    setComponentName("");
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedComponentName = componentName.trim();
    if (!trimmedComponentName) {
      setError("Component name is required.");
      return;
    }
    if (!/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(trimmedComponentName)) {
      setError(
        "Component name must start with a letter and can only contain letters, numbers, hyphens (-), and underscores (_)."
      );
      return;
    }
    setError(null);
    await onInstall(trimmedComponentName);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="installModalTitle"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/70 backdrop-blur-sm p-4"
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 max-w-md w-full p-6">
        <div className="flex justify-between items-center pb-3 border-b border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50 -m-6 p-4 rounded-t-lg mb-4">
          <h2
            id="installModalTitle"
            className="text-lg font-semibold text-gray-800 dark:text-gray-100"
          >
            Install Plugin: <span className="font-bold">{pluginName}</span>
          </h2>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 p-1 rounded-full focus-visible:ring-2 focus-visible:ring-blue-500"
            aria-label="Close modal"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="componentName">Component Name:</Label>
            <Input
              type="text"
              id="componentName"
              value={componentName}
              onChange={(e) => {
                setComponentName(e.target.value);
                if (error) setError(null);
              }}
              placeholder="e.g., my-new-plugin"
              disabled={isLoading}
              required
            />
            {error && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {error}
              </p>
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              This name will be used for the component configuration file.
            </p>
          </div>

          <div className="mt-6 flex justify-end space-x-3 pt-4 border-t border-gray-200 dark:border-gray-600">
            <Button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              variant="default"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || !componentName.trim()}
              variant="primary"
            >
              {isLoading ? "Installing..." : "Install Plugin"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default InstallPluginModal;
