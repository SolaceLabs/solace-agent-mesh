import { useState } from "react";
import Button from "../../ui/Button";
import TutorialCard from "./TutorialCard";
import DocResourceCard from "./DocResourceCard";

function CopyButton({ text }: { readonly text: string }) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  const renderCopyIcon = () => {
    if (isCopied) {
      return (
        <svg
          className="w-5 h-5 text-green-500 transition-all duration-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
      );
    }

    return (
      <svg
        className="w-5 h-5 transition-all duration-300"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
        />
      </svg>
    );
  };

  return (
    <button
      onClick={handleCopy}
      className="text-white transition-colors opacity-100"
      aria-label={isCopied ? "Copied" : "Copy to clipboard"}
    >
      {renderCopyIcon()}
    </button>
  );
}

interface SuccessScreenProps {
  title?: string;
  message?: string;
  initTab?: string;
}

export default function SuccessScreen({
  title,
  message,
  initTab,
}: SuccessScreenProps) {
  const [activeTab, setActiveTab] = useState(initTab ?? "getting-started");
  const tabCount = 3;
  const currentTabIndex =
    activeTab === "getting-started" ? 0 : activeTab === "tutorials" ? 1 : 2;

  const defaultTitle = "Operation Successful!";
  const defaultMessage =
    "Your configuration has been saved. You're now ready to proceed.";

  const getNextTabName = (index: number) => {
    if (index === 0) return "tutorials";
    if (index === 1) return "documentation";
    return "getting-started";
  };

  const getPreviousTabName = (index: number) => {
    if (index === 1) return "getting-started";
    if (index === 2) return "tutorials";
    return "documentation";
  };

  const goToNextTab = () => {
    if (currentTabIndex < tabCount - 1) {
      const nextTab = getNextTabName(currentTabIndex);
      setActiveTab(nextTab);
    }
  };

  const goToPreviousTab = () => {
    if (currentTabIndex > 0) {
      const prevTab = getPreviousTabName(currentTabIndex);
      setActiveTab(prevTab);
    }
  };

  const getTabButtonClass = (tabName: string) => {
    const baseClass = "px-4 py-3 text-sm font-medium ";
    if (activeTab === tabName) {
      return baseClass + "text-solace-blue border-b-2 border-solace-blue";
    }
    return baseClass + "text-gray-500 hover:text-solace-blue";
  };

  const tutorials = [
    {
      icon: "🌤️",
      title: "Weather Agent",
      description:
        "Build an agent that gives Solace Agent Mesh the ability to access real-time weather information.",
      time: "~5 min",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/tutorials/custom-agent",
    },
    {
      icon: "🗃️",
      title: "SQL Database Integration",
      description:
        "Enable Solace Agent Mesh to answer company-specific questions using a sample coffee company database.",
      time: "~10-15 min",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/tutorials/sql-database",
    },
    {
      icon: "🧠",
      title: "MCP Integration",
      description:
        "Integrating a Model Context Protocol (MCP) Server into Solace Agent Mesh.",
      time: "~10-15 min",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/tutorials/mcp-integration",
    },
    {
      icon: "💬",
      title: "Slack Integration",
      description: "Chat with Solace Agent Mesh directly from Slack.",
      time: "~20-30 min",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/tutorials/slack-integration",
    },
  ];

  const docResources = [
    {
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      ),
      title: "Getting Started",
      description: "Introduction and basic concepts",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/",
    },
    {
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
          />
        </svg>
      ),
      title: "Architecture",
      description: "System architecture and design",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/architecture",
    },
    {
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122"
          />
        </svg>
      ),
      title: "Tutorials",
      description: "Step-by-step guides",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/tutorials/custom-agent",
    },
    {
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      ),
      title: "Developing",
      description: "Development guides for various components",
      link: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/developing/",
    },
  ];

  const renderTabContent = () => {
    if (activeTab === "getting-started") {
      return (
        <div className="space-y-6">
          <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
            <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 mr-2 text-solace-blue"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.002z" />
              </svg>
              Your Configuration Files
            </h3>
            <p className="text-gray-600 mb-4">
              Your configurations have been saved in the following files:
            </p>
            <div className="flex space-x-4 mb-4">
              <div className="bg-gray-50 px-4 py-3 rounded-md border border-gray-200 flex-1 flex items-center">
                <code className="text-solace-blue font-mono">.env</code>
                <span className="ml-3 text-gray-500 text-sm">
                  Environment variables
                </span>
              </div>
              <div className="bg-gray-50 px-4 py-3 rounded-md border border-gray-200 flex-1 flex items-center">
                <code className="text-solace-blue font-mono">
                  configs/shared_config.yaml
                </code>
                <span className="ml-3 text-gray-500 text-sm">Config file</span>
              </div>
            </div>
          </div>
          <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
            <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 mr-2 text-solace-blue"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
              Start the Service
            </h3>
            <p className="text-gray-600 mb-4">
              To start Solace Agent Mesh directly, return to your terminal and run:
            </p>
            <div className="bg-gray-800 text-gray-200 p-4 rounded-md font-mono text-sm mb-4 flex items-center justify-between group relative">
              <code>sam run</code>
              <CopyButton text="sam run" />
            </div>

            <p className="text-gray-600">
              You can use{" "}
              <code className="bg-gray-100 px-1 py-0.5 rounded">sam</code> as a
              shorthand for{" "}
              <code className="bg-gray-100 px-1 py-0.5 rounded">
                solace-agent-mesh
              </code>{" "}
              in all commands.
            </p>
          </div>
        </div>
      );
    }

    if (activeTab === "tutorials") {
      return (
        <div>
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-800 mb-2">
              Hands-on Tutorials
            </h3>
            <p className="text-gray-600">
              Ready to go further? Here are some practical tutorials to help you
              leverage the full potential of Solace Agent Mesh.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {tutorials.map((tutorial) => (
              <TutorialCard
                key={tutorial.title}
                icon={tutorial.icon}
                title={tutorial.title}
                description={tutorial.description}
                time={tutorial.time}
                link={tutorial.link}
              />
            ))}
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
          <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 mr-2 text-solace-blue"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
            Documentation Resources
          </h3>
          <p className="text-gray-600 mb-6">
            Explore our comprehensive documentation to get the most out of
            Solace Agent Mesh:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {docResources.map((resource) => (
              <DocResourceCard
                key={resource.title}
                icon={resource.icon}
                title={resource.title}
                description={resource.description}
                link={resource.link}
              />
            ))}
          </div>

          <div className="mt-6 text-center">
            <a
              href="https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-5 py-2 rounded-md bg-solace-blue text-white hover:bg-solace-blue-dark transition-colors"
            >
              View Documentation
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 ml-2"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M14 5l7 7m0 0l-7 7m7-7H3"
                />
              </svg>
            </a>
          </div>
        </div>

        <div className="p-6 bg-gradient-to-b from-solace-blue-light to-blue-50 rounded-lg text-center">
          <h3 className="text-lg font-medium text-solace-blue mb-2">
            Connect with the Community
          </h3>
          <p className="text-gray-600 mb-4">
            Solace Agent Mesh is open source! We welcome contributions and
            discussions from the community.
          </p>

          <div className="mt-6 flex flex-col sm:flex-row justify-center items-stretch gap-4">
            <a
              href="https://github.com/SolaceLabs/solace-agent-mesh"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-1/2 p-4 rounded-md bg-white text-solace-blue border border-solace-blue hover:bg-solace-blue hover:text-white transition-colors flex flex-col items-center justify-center group"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="32"
                height="32"
                viewBox="0 0 24 24"
                className="mb-2 text-solace-blue group-hover:text-white transition-colors"
              >
                <path
                  d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
                  fill="currentColor"
                />
              </svg>
              <span className="font-medium">GitHub Repository</span>
            </a>

            <a
              href="https://solace.community/c/solace-agent-mesh/16"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-1/2 p-4 rounded-md bg-white text-solace-blue border border-solace-blue hover:bg-solace-blue hover:text-white transition-colors flex flex-col items-center justify-center group"
            >
              <img
                src="data:image/png;data:image/png;base64,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"
                alt="Solace Community Forum Logo"
                className="max-h-8 mb-2 object-contain"
              />
              <span className="font-medium">Community Forum</span>
            </a>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="p-8 bg-gradient-to-br from-green-50 to-blue-50 rounded-xl mb-8 text-center relative overflow-hidden">
        <div className="relative z-10">
          <div className="inline-block bg-green-100 p-3 rounded-full mb-4">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-10 w-10 text-green-600"
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
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">
            {title || defaultTitle}
          </h2>
          <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
            {message || defaultMessage}
          </p>
          <div className="inline-flex items-center px-4 py-2 bg-solace-blue text-white rounded-full shadow-sm">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5 mr-2"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z"
                clipRule="evenodd"
              />
            </svg>
            Configuration saved successfully
          </div>
        </div>
        <div className="absolute top-0 right-0 -mt-10 -mr-10 h-40 w-40 bg-green-200 opacity-50 rounded-full"></div>
        <div className="absolute bottom-0 left-0 -mb-10 -ml-10 h-32 w-32 bg-green-200 opacity-50 rounded-full"></div>
      </div>

      <div className="flex items-center mb-6 border-b">
        <div className="flex-1 flex">
          <button
            onClick={() => setActiveTab("getting-started")}
            className={getTabButtonClass("getting-started")}
          >
            Getting Started
          </button>
          <button
            onClick={() => setActiveTab("tutorials")}
            className={getTabButtonClass("tutorials")}
          >
            Tutorials
          </button>
          <button
            onClick={() => setActiveTab("documentation")}
            className={getTabButtonClass("documentation")}
          >
            Documentation
          </button>
        </div>
        <div className="text-gray-500 text-sm mr-4 flex items-center">
          Page {currentTabIndex + 1} of {tabCount}
        </div>
      </div>

      {renderTabContent()}

      <div className="mt-8 flex justify-between items-center">
        <div className="text-sm text-gray-500">
          <span className="md:hidden">
            Page {currentTabIndex + 1} of {tabCount}
          </span>
        </div>
        <div className="flex space-x-4">
          <div className="w-24">
            {currentTabIndex > 0 && (
              <Button
                onClick={goToPreviousTab}
                variant="outline"
                type="button"
              >
                Previous
              </Button>
            )}
          </div>
          <div className="w-20">
            {currentTabIndex < tabCount - 1 && (
              <Button
                onClick={goToNextTab}
                type="button"
              >
                Next
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
