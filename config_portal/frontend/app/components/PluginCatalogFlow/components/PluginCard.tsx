import React from "react";
import { PluginViewData } from "../types";
import { Box, GitMerge, CheckCircle, Tag, Cpu, Server, Wrench } from "lucide-react";

const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary";
    className?: string;
  }
> = ({ variant = "secondary", className, children, ...props }) => {
  const baseStyle =
    "px-3 py-1.5 text-xs rounded font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none";
  const primaryStyle = "bg-green-500 hover:bg-green-600 text-white dark:bg-green-600 dark:hover:bg-green-700";
  const secondaryStyle =
    "bg-gray-200 hover:bg-gray-300 text-gray-700 dark:bg-gray-600 dark:hover:bg-gray-500 dark:text-gray-200";

  return (
    <button
      {...props}
      className={`${baseStyle} ${variant === "primary" ? primaryStyle : secondaryStyle} ${className || ""}`}>
      {children}
    </button>
  );
};

interface PluginCardProps {
  plugin: PluginViewData;
  onReadMore: () => void;
  onInstall: () => void;
}

const DetailItem: React.FC<{
  label: string;
  value?: string | null;
  icon?: React.ReactNode;
}> = ({ label, value, icon }) => {
  if (value === undefined || value === null || (typeof value === "string" && !value.trim())) return null;
  return (
    <div className="flex items-center text-xs mb-1">
      <div className="flex items-center font-medium text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">
        {icon && <span className="mr-1.5">{icon}</span>}
        {label}:
      </div>
      <div className="text-gray-700 dark:text-gray-200 truncate" title={value}>
        {value}
      </div>
    </div>
  );
};

const PluginCard: React.FC<PluginCardProps> = ({ plugin, onReadMore, onInstall }) => {
  const description = plugin.pyproject.description || "No description available.";

  const getTypeIcon = (type?: string | null) => {
    switch (type?.toLowerCase()) {
      case "agent":
        return <Cpu size={12} />;
      case "gateway":
        return <Server size={12} />;
      case "tool":
        return <Wrench size={12} />;
      default:
        return <Tag size={12} />;
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 shadow-xl rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col h-[280px]">
      <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
        <div className="flex items-center min-w-0">
          <Box className="w-5 h-5 text-blue-500 dark:text-blue-400 mr-2 flex-shrink-0" />
          <h2 className="text-md font-semibold text-gray-800 dark:text-gray-100 truncate" title={plugin.pyproject.name}>
            {plugin.pyproject.name}
          </h2>
        </div>
        {plugin.is_official && (
          <span title="Verified Official Plugin" className="ml-2 flex-shrink-0">
            <CheckCircle className="w-4 h-4 text-green-500 dark:text-green-400" />
          </span>
        )}
      </div>

      <div className="p-3 space-y-2 overflow-y-auto flex-grow scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 scrollbar-track-gray-100 dark:scrollbar-track-gray-700">
        <DetailItem label="Version" value={plugin.pyproject.version} icon={<GitMerge size={12} />} />
        <DetailItem
          label="Type"
          value={plugin.pyproject.plugin_type || "custom"}
          icon={getTypeIcon(plugin.pyproject.plugin_type)}
        />
        <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-3" title={description}>
          {description}
        </p>
      </div>

      <div className="flex justify-end space-x-2 p-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
        <Button onClick={onReadMore} variant="secondary">
          More
        </Button>
        <Button onClick={onInstall} variant="primary">
          Install
        </Button>
      </div>
    </div>
  );
};
export default PluginCard;
