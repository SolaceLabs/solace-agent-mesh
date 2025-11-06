import React, { useState, useEffect, useCallback } from "react";
import { PluginViewData, RegistryViewData } from "./types";
import PluginCard from "./components/PluginCard";
import ReadMoreModal from "./components/ReadMoreModal";
import InstallPluginModal from "./components/InstallPluginModal";
import AddRegistryModal from "./components/AddRegistryModal";

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
  const secondaryStyle =
    "bg-indigo-600 hover:bg-indigo-700 text-white dark:bg-indigo-500 dark:hover:bg-indigo-600";
  const defaultStyle =
    "bg-gray-200 hover:bg-gray-300 text-gray-800 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-100";

  let styleVariant = defaultStyle;
  if (variant === "primary") styleVariant = primaryStyle;
  else if (variant === "secondary") styleVariant = secondaryStyle;

  return (
    <button
      {...props}
      className={`${baseStyle} ${styleVariant} ${className || ""}`}
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

const Select: React.FC<
  React.SelectHTMLAttributes<HTMLSelectElement> & { className?: string }
> = ({ className, children, ...props }) => (
  <select
    {...props}
    className={`flex h-10 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 focus-visible:ring-offset-1 dark:focus-visible:ring-offset-gray-800 disabled:cursor-not-allowed disabled:opacity-50 ${
      className || ""
    }`}
  >
    {children}
  </select>
);

const Spinner: React.FC = () => (
  <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
);

const Alert: React.FC<{
  variant: "success" | "destructive";
  title?: string;
  description: string;
  className?: string;
}> = ({ variant, title, description, className }) => {
  const baseClasses = "relative w-full rounded-lg border p-4";
  const successClasses =
    "bg-green-50 dark:bg-green-900/30 border-green-500/50 text-green-700 dark:text-green-300";
  const destructiveClasses =
    "bg-red-50 dark:bg-red-900/30 border-red-500/50 text-red-700 dark:text-red-300";
  return (
    <div
      role="alert"
      className={`${baseClasses} ${
        variant === "destructive" ? destructiveClasses : successClasses
      } ${className || ""}`}
    >
      {title && (
        <h5 className="mb-1 font-semibold leading-none tracking-tight">
          {title}
        </h5>
      )}
      <div className="text-sm opacity-90">{description}</div>
    </div>
  );
};

const PluginCatalogFlow: React.FC = () => {
  const [plugins, setPlugins] = useState<PluginViewData[]>([]);
  const [filteredPlugins, setFilteredPlugins] = useState<PluginViewData[]>([]);
  const [, setRegistries] = useState<RegistryViewData[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<
    "all" | "agents" | "gateways" | "tools" | "custom"
  >("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notification, setNotification] = useState<{
    type: "success" | "destructive";
    message: string;
  } | null>(null);

  const [selectedPluginForModal, setSelectedPluginForModal] =
    useState<PluginViewData | null>(null);
  const [isReadMoreModalOpen, setIsReadMoreModalOpen] = useState(false);
  const [pluginToInstall, setPluginToInstall] = useState<PluginViewData | null>(
    null
  );
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
  const [isAddRegistryModalOpen, setIsAddRegistryModalOpen] = useState(false);

  const fetchPlugins = useCallback(async (showLoading: boolean = true) => {
    if (showLoading) setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/plugin_catalog/plugins");
      if (!response.ok)
        throw new Error(
          `Failed to fetch plugins: ${response.statusText} (${response.status})`
        );
      const data: PluginViewData[] = await response.json();
      setPlugins(data);
      setFilteredPlugins(data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      setError(errorMessage);
      handleShowNotification("destructive", errorMessage);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  const fetchRegistries = useCallback(async () => {
    try {
      const response = await fetch("/api/plugin_catalog/registries");
      if (!response.ok) throw new Error("Failed to fetch registries");
      const data: RegistryViewData[] = await response.json();
      setRegistries(data);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      console.error("Failed to fetch registries:", errorMessage);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
    fetchRegistries();
  }, [fetchPlugins, fetchRegistries]);

  useEffect(() => {
    const lowerSearchTerm = searchTerm.toLowerCase();
    setFilteredPlugins(
      plugins.filter((p) => {
        const matchesSearch =
          p.pyproject.name.toLowerCase().includes(lowerSearchTerm) ||
          (p.pyproject.description &&
            p.pyproject.description.toLowerCase().includes(lowerSearchTerm));

        const pluginType = p.pyproject.plugin_type?.toLowerCase() || "custom";
        const matchesType =
          typeFilter === "all" ||
          (typeFilter === "agents" && pluginType === "agent") ||
          (typeFilter === "gateways" && pluginType === "gateway") ||
          (typeFilter === "tools" && pluginType === "tool") ||
          (typeFilter === "custom" && pluginType === "custom");

        return matchesSearch && matchesType;
      })
    );
  }, [searchTerm, typeFilter, plugins]);

  const handleShowNotification = (
    type: "success" | "destructive",
    message: string
  ) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 7000);
  };

  const handleReadMore = (plugin: PluginViewData) => {
    setSelectedPluginForModal(plugin);
    setIsReadMoreModalOpen(true);
  };

  const handleInstallClick = (plugin: PluginViewData) => {
    setPluginToInstall(plugin);
    setIsInstallModalOpen(true);
  };

  const handleInstallConfirm = async (componentName: string) => {
    if (!pluginToInstall) return;
    setIsLoading(true);
    try {
      const response = await fetch("/api/plugin_catalog/plugins/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pluginId: pluginToInstall.id, componentName }),
      });
      const result = await response.json();
      if (!response.ok || result.status === "failure") {
        throw new Error(result.error || "Installation failed");
      }
      handleShowNotification(
        "success",
        result.message || "Plugin installed successfully!"
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      handleShowNotification("destructive", errorMessage);
    } finally {
      setIsLoading(false);
      setIsInstallModalOpen(false);
      setPluginToInstall(null);
    }
  };

  const handleRefreshRegistries = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/plugin_catalog/registries/refresh", {
        method: "POST",
      });
      const result = await response.json();
      if (!response.ok || result.status !== "success") {
        throw new Error(result.message || "Failed to refresh registries");
      }
      handleShowNotification("success", result.message);
      await fetchPlugins(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      setError(errorMessage);
      handleShowNotification("destructive", errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddRegistry = async (pathOrUrl: string, name?: string) => {
    setIsLoading(true);
    try {
      const payload: { path_or_url: string; name?: string } = {
        path_or_url: pathOrUrl,
      };
      if (name && name.trim() !== "") {
        payload.name = name.trim();
      }
      const response = await fetch("/api/plugin_catalog/registries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json();
      if (!response.ok || result.status !== "success") {
        throw new Error(result.error || "Failed to add registry");
      }
      handleShowNotification("success", result.message);
      await fetchRegistries();
      await fetchPlugins(false);
      setIsAddRegistryModalOpen(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      handleShowNotification("destructive", errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-100 dark:bg-gray-900 overflow-auto">
      <div className="p-4 md:p-6 lg:p-8">
        <header className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-gray-800 dark:text-gray-100">
            SAM Plugin Catalog
          </h1>
        </header>

        {notification && (
          <Alert
            variant={notification.type}
            description={notification.message}
            className="mb-6"
          />
        )}
        {error && !notification && (
          <Alert
            variant="destructive"
            title="Error"
            description={error}
            className="mb-6"
          />
        )}

        <div className="mb-8 p-4 bg-white dark:bg-gray-800 shadow-md rounded-lg">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex flex-col sm:flex-row gap-3 w-full md:flex-grow">
              <Input
                type="text"
                placeholder="Search plugins by name or description..."
                value={searchTerm}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setSearchTerm(e.target.value)
                }
                className="w-full sm:flex-grow"
              />
              <Select
                value={typeFilter}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                  setTypeFilter(
                    e.target.value as "all" | "agents" | "gateways" | "custom"
                  )
                }
                className="w-full sm:w-auto sm:min-w-[140px]"
              >
                <option value="all">All Types</option>
                <option value="agents">Agents</option>
                <option value="gateways">Gateways</option>
                <option value="tools">Tools</option>
                <option value="custom">Custom</option>
              </Select>
            </div>
            <div className="flex gap-3 flex-shrink-0">
              <Button
                onClick={() => setIsAddRegistryModalOpen(true)}
                variant="primary"
              >
                + Add Registry
              </Button>
              <Button
                onClick={handleRefreshRegistries}
                disabled={isLoading && plugins.length === 0}
                variant="secondary"
              >
                {isLoading && plugins.length === 0 ? (
                  <Spinner />
                ) : (
                  "Refresh All"
                )}
              </Button>
            </div>
          </div>
        </div>

        {isLoading && plugins.length === 0 && (
          <div className="flex flex-col justify-center items-center mt-12 h-64 text-gray-500 dark:text-gray-400">
            <Spinner />
            <p className="ml-3 mt-3 text-lg">Loading plugins...</p>
          </div>
        )}

        {!isLoading &&
          plugins.length > 0 &&
          filteredPlugins.length === 0 &&
          searchTerm && (
            <p className="text-center text-gray-600 dark:text-gray-400 mt-12 text-lg">
              No plugins found matching your search criteria.
            </p>
          )}
        {!isLoading && plugins.length === 0 && !error && (
          <p className="text-center text-gray-600 dark:text-gray-400 mt-12 text-lg">
            No plugins found. Try adding a new registry or click &#34;Refresh
            All&#34;.
          </p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredPlugins.map((plugin) => (
            <PluginCard
              key={plugin.id}
              plugin={plugin}
              onReadMore={() => handleReadMore(plugin)}
              onInstall={() => handleInstallClick(plugin)}
            />
          ))}
        </div>

        {isReadMoreModalOpen && selectedPluginForModal && (
          <ReadMoreModal
            plugin={selectedPluginForModal}
            isOpen={isReadMoreModalOpen}
            onClose={() => setIsReadMoreModalOpen(false)}
            onInstall={handleInstallClick}
          />
        )}
        {isInstallModalOpen && pluginToInstall && (
          <InstallPluginModal
            pluginName={pluginToInstall.pyproject.name}
            isOpen={isInstallModalOpen}
            onClose={() => setIsInstallModalOpen(false)}
            onInstall={handleInstallConfirm}
            isLoading={isLoading}
          />
        )}
        {isAddRegistryModalOpen && (
          <AddRegistryModal
            isOpen={isAddRegistryModalOpen}
            onClose={() => setIsAddRegistryModalOpen(false)}
            onAddRegistry={handleAddRegistry}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  );
};

export default PluginCatalogFlow;
