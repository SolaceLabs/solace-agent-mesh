import React from "react";
import { PluginViewData, AgentCardSkill } from "../types";
import ReactMarkdown from "react-markdown";

const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "default";
    className?: string;
  }
> = ({ variant = "default", className, children, ...props }) => {
  const baseStyle =
    "px-4 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-800 disabled:opacity-50 disabled:pointer-events-none";
  const primaryStyle =
    "bg-green-500 hover:bg-green-600 text-white dark:bg-green-600 dark:hover:bg-green-700";
  const secondaryStyle =
    "bg-indigo-600 hover:bg-indigo-700 text-white dark:bg-indigo-500 dark:hover:bg-indigo-600";
  const defaultStyle =
    "bg-gray-200 hover:bg-gray-300 text-gray-800 dark:bg-gray-600 dark:hover:bg-gray-500 dark:text-gray-100";

  let currentStyle = defaultStyle;
  if (variant === "primary") {
    currentStyle = primaryStyle;
  } else if (variant === "secondary") {
    currentStyle = secondaryStyle;
  }

  return (
    <button
      {...props}
      className={`${baseStyle} ${currentStyle} ${className || ""}`.trim()}
    >
      {children}
    </button>
  );
};

interface ReadMoreModalProps {
  plugin: PluginViewData;
  isOpen: boolean;
  onClose: () => void;
  onInstall: (plugin: PluginViewData) => void;
}

const ReadMoreModal: React.FC<ReadMoreModalProps> = ({
  plugin,
  isOpen,
  onClose,
  onInstall,
}) => {
  if (!isOpen) {
    return null;
  }

  const renderSkills = (skills: AgentCardSkill[] | undefined | null) => {
    if (!skills || skills.length === 0) {
      return (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No skills defined for this plugin.
        </p>
      );
    }
    return (
      <ul className="list-disc list-inside space-y-1 pl-1">
        {skills.map((skill, index) => (
          <li key={index} className="text-sm text-gray-700 dark:text-gray-300">
            <strong className="font-semibold text-gray-800 dark:text-gray-200">
              {skill.name || "Unnamed Skill"}
            </strong>
            {skill.description && `: ${skill.description}`}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div
      role="button"
      tabIndex={-1}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClose();
      }}
    >
      <div
        role="dialog"
        className="bg-white dark:bg-gray-800 rounded-lg shadow-2xl border border-gray-200 dark:border-gray-700 max-w-2xl w-full max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          e.stopPropagation();
        }}
      >
        <div className="flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50">
          <h2
            id="readMoreModalTitle"
            className="text-xl font-semibold text-gray-800 dark:text-gray-100"
          >
            {plugin.pyproject.name}{" "}
            <span className="text-xs text-gray-500 dark:text-gray-400">
              v{plugin.pyproject.version}
            </span>
          </h2>
          <button
            onClick={onClose}
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

        <div className="p-5 space-y-5 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 scrollbar-track-gray-100 dark:scrollbar-track-gray-700 flex-grow">
          <div>
            <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
              Description
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {plugin.pyproject.description || "No description provided."}
            </p>
          </div>

          {plugin.pyproject.authors && plugin.pyproject.authors.length > 0 && (
            <div>
              <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Author(s)
              </h3>
              <ul className="list-disc list-inside pl-1">
                {plugin.pyproject.authors.map((author, index) => (
                  <li
                    key={index}
                    className="text-sm text-gray-600 dark:text-gray-400"
                  >
                    {author.name || "N/A"}{" "}
                    {author.email && (
                      <span className="text-gray-500 dark:text-gray-400">{`<${author.email}>`}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {plugin.pyproject.custom_metadata &&
            Object.keys(plugin.pyproject.custom_metadata).length > 0 && (
              <div>
                <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                  Additional Metadata
                </h3>
                <div className="p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-600 space-y-2">
                  <ul className="space-y-1">
                    {Object.entries(plugin.pyproject.custom_metadata).map(
                      ([key, value]) => (
                        <li
                          key={key}
                          className="text-sm text-gray-700 dark:text-gray-300 flex"
                        >
                          <strong className="font-medium w-1/3 min-w-[100px] flex-shrink-0 text-gray-600 dark:text-gray-200 break-words">
                            {key}:
                          </strong>
                          <span className="text-gray-600 dark:text-gray-400 break-words">
                            {String(value)}
                          </span>
                        </li>
                      )
                    )}
                  </ul>
                </div>
              </div>
            )}

          {plugin.agent_card ? (
            <div>
              <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
                Agent Card Details
              </h3>
              <div className="p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-600 space-y-2">
                {plugin.agent_card.displayName && (
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    <strong className="font-medium text-gray-700 dark:text-gray-200">
                      Display Name:
                    </strong>{" "}
                    {plugin.agent_card.displayName}
                  </p>
                )}
                {plugin.agent_card.shortDescription && (
                  <p className="text-sm mt-1 text-gray-600 dark:text-gray-300">
                    <strong className="font-medium text-gray-700 dark:text-gray-200">
                      Card Description:
                    </strong>{" "}
                    {plugin.agent_card.shortDescription}
                  </p>
                )}

                {plugin.agent_card.Skill &&
                  plugin.agent_card.Skill.length > 0 && (
                    <div className="mt-2.5">
                      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-1">
                        Skills:
                      </h4>
                      {renderSkills(plugin.agent_card.Skill)}
                    </div>
                  )}
                {!plugin.agent_card.displayName &&
                  !plugin.agent_card.shortDescription &&
                  (!plugin.agent_card.Skill ||
                    plugin.agent_card.Skill.length === 0) && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      No specific agent card details provided.
                    </p>
                  )}
              </div>
            </div>
          ) : (
            <div className="p-3 bg-gray-100 dark:bg-gray-700/30 rounded-md border border-gray-200 dark:border-gray-600">
              <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1">
                Agent Card Details
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No agent card data available for this plugin.
              </p>
            </div>
          )}

          <div>
            <h3 className="text-md font-semibold text-gray-700 dark:text-gray-200 mb-1.5">
              README
            </h3>
            {plugin.readme_content ? (
              <div className="p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-200 dark:border-slate-600 space-y-2 text-gray-700 dark:text-gray-200">
                <ReactMarkdown>{plugin.readme_content}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No README content available.
              </p>
            )}
          </div>

          <div className="text-xs text-gray-500 dark:text-gray-400 mt-4 pt-3 border-t border-gray-200 dark:border-gray-600 space-y-1">
            <p>
              <strong className="text-gray-600 dark:text-gray-300">
                Source:
              </strong>{" "}
              {plugin.source_registry_name || "Unnamed Registry"} (
              {plugin.source_type})
            </p>
            <p>
              <strong className="text-gray-600 dark:text-gray-300">
                Location:
              </strong>{" "}
              {plugin.source_type === "git" ? (
                <a
                  href={plugin.source_registry_location}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 dark:text-blue-400 hover:underline break-all"
                >
                  {plugin.source_registry_location}
                </a>
              ) : (
                <span className="break-all">
                  {plugin.source_registry_location}
                </span>
              )}
            </p>
            <p>
              <strong className="text-gray-600 dark:text-gray-300">
                Plugin Subpath:
              </strong>{" "}
              {plugin.plugin_subpath}
            </p>
          </div>
        </div>

        <div className="mt-auto p-4 border-t border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/50 flex justify-end space-x-3">
          <Button onClick={onClose} variant="default">
            Close
          </Button>
          <Button onClick={() => onInstall(plugin)} variant="primary">
            Install
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ReadMoreModal;
