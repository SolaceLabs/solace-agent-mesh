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
    "bg-blue-600 hover:bg-blue-700 text-white dark:bg-blue-500 dark:hover:bg-blue-600";
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

interface AddRegistryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddRegistry: (pathOrUrl: string, name?: string) => Promise<void>;
  isLoading?: boolean;
}

const AddRegistryModal: React.FC<AddRegistryModalProps> = ({
  isOpen,
  onClose,
  onAddRegistry,
  isLoading = false,
}) => {
  const [registryPathOrUrl, setRegistryPathOrUrl] = useState("");
  const [registryName, setRegistryName] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPathOrUrl = registryPathOrUrl.trim();
    const trimmedName = registryName.trim();

    if (!trimmedPathOrUrl) {
      setError("Registry Path or URL is required.");
      return;
    }
    setError(null);
    await onAddRegistry(
      trimmedPathOrUrl,
      trimmedName === "" ? undefined : trimmedName
    );
  };

  const handleClose = () => {
    setRegistryPathOrUrl("");
    setRegistryName("");
    setError(null);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="addRegistryModalTitle"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/70 backdrop-blur-sm p-4"
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 max-w-md w-full p-6">
        <div className="flex justify-between items-center pb-3 border-b border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50 -m-6 p-4 rounded-t-lg mb-4">
          <h2
            id="addRegistryModalTitle"
            className="text-lg font-semibold text-gray-800 dark:text-gray-100"
          >
            Add New Plugin Registry
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

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <Label htmlFor="registryPathOrUrl">Registry Path or URL:</Label>
            <Input
              type="text"
              id="registryPathOrUrl"
              value={registryPathOrUrl}
              onChange={(e) => {
                setRegistryPathOrUrl(e.target.value);
                if (error) setError(null);
              }}
              placeholder="https://github.com/user/plugins.git or /path/to/local/plugins"
              disabled={isLoading}
              required
            />
            {error && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                {error}
              </p>
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Enter a Git URL (HTTPS/Git) or an absolute local filesystem path.
            </p>
          </div>

          <div>
            <Label htmlFor="registryName">Registry Name (Optional):</Label>
            <Input
              type="text"
              id="registryName"
              value={registryName}
              onChange={(e) => setRegistryName(e.target.value)}
              placeholder="My Custom Plugins"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              An optional name for this registry. If blank, a name will be
              derived.
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
              disabled={isLoading || !registryPathOrUrl.trim()}
              variant="primary"
            >
              {isLoading ? "Adding..." : "Add Registry"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddRegistryModal;
