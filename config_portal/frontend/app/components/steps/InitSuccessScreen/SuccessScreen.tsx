import { useState } from 'react';
import Button from '../../ui/Button';
import TutorialCard from './TutorialCard';
import DocResourceCard from './DocResourceCard';

//copy button component with copy state animation
function CopyButton({ text }: { readonly text: string }) {
  const [isCopied, setIsCopied] = useState(false);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };
  
  //icon rendering
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

export default function SuccessScreen() {
  const [activeTab, setActiveTab] = useState('getting-started');
  const tabCount = 3;
  const currentTabIndex = activeTab === 'getting-started' ? 0 : activeTab === 'tutorials' ? 1 : 2;
  
  const getNextTabName = (index: number) => {
    if (index === 0) return 'tutorials';
    if (index === 1) return 'documentation';
    return 'getting-started';
  };
  
  //logic for determining the previous tab
  const getPreviousTabName = (index: number) => {
    if (index === 1) return 'getting-started';
    if (index === 2) return 'tutorials';
    return 'documentation';
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
  
  // tab button class logic
  const getTabButtonClass = (tabName: string) => {
    const baseClass = "px-4 py-3 text-sm font-medium ";
    if (activeTab === tabName) {
      return baseClass + "text-solace-blue border-b-2 border-solace-blue";
    }
    return baseClass + "text-gray-500 hover:text-solace-blue";
  };
  
  const tutorials = [
    {
      icon: '🌤️',
      title: 'Weather Agent',
      description: 'Build an agent that gives Solace Agent Mesh the ability to access real-time weather information.',
      time: '~5 min',
      link: 'https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/tree/main/sam-geo-information'
    },
    {
      icon: '🗃️',
      title: 'SQL Database Integration',
      description: 'Enable Solace Agent Mesh to answer company-specific questions using a sample coffee company database.',
      time: '~10-15 min',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/sql-database'
    },
    {
      icon: '🧠',
      title: 'MCP Integration',
      description: 'Integrating a Model Context Protocol (MCP) Server into Solace Agent Mesh.',
      time: '~10-15 min',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/mcp-integration'
    },
    {
      icon: '💬',
      title: 'Slack Integration',
      description: 'Chat with Solace Agent Mesh directly from Slack.',
      time: '~20-30 min',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/slack-integration'
    }
  ];
  
  // Configurable documentation resources
  const docResources = [
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      title: 'Getting Started',
      description: 'Introduction and basic concepts',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/'
    },
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
        </svg>
      ),
      title: 'Architecture',
      description: 'System architecture and design',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/component-overview'
    },
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
        </svg>
      ),
      title: 'Tutorials',
      description: 'Step-by-step guides',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/event-mesh-gateway'
    },
    {
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      title: 'User Guides',
      description: 'User Guides for various components',
      link: 'https://solacelabs.github.io/solace-agent-mesh/docs/documentation/user-guide/solace-ai-connector'
    }
  ];
  
  // Function to render active tab content
  const renderTabContent = () => {
    if (activeTab === 'getting-started') {
      return (
        <div className="space-y-6">
          <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
            <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-solace-blue" viewBox="0 0 20 20" fill="currentColor">
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
                <span className="ml-3 text-gray-500 text-sm">Environment variables</span>
              </div>
              <div className="bg-gray-50 px-4 py-3 rounded-md border border-gray-200 flex-1 flex items-center">
                <code className="text-solace-blue font-mono">solace-agent-mesh.yaml</code>
                <span className="ml-3 text-gray-500 text-sm">Configuration file</span>
              </div>
            </div>
          </div>
          <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
            <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-solace-blue" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
              Start the Service
            </h3>
            <p className="text-gray-600 mb-4">
              To start Solace Agent Mesh directly, run:
            </p>
            <div className="bg-gray-800 text-gray-200 p-4 rounded-md font-mono text-sm mb-4 flex items-center justify-between group relative">
              <code>sam run -b</code>
              <CopyButton text="sam run -b" />
            </div>
            
            <p className="text-gray-600">
              You can use <code className="bg-gray-100 px-1 py-0.5 rounded">sam</code> as a shorthand for <code className="bg-gray-100 px-1 py-0.5 rounded">solace-agent-mesh</code> in all commands.
            </p>
          </div>
        </div>
      );
    }
    
    if (activeTab === 'tutorials') {
      return (
        <div>
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-800 mb-2">Hands-on Tutorials</h3>
            <p className="text-gray-600">
              Ready to go further? Here are some practical tutorials to help you leverage the full potential of Solace Agent Mesh.
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
    
    // Documentation tab (default fallback)
    return (
      <div className="space-y-6">
        <div className="p-6 bg-white rounded-lg shadow-sm border border-gray-100">
          <h3 className="text-lg font-medium text-gray-800 mb-4 flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-solace-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Documentation Resources
          </h3>
          <p className="text-gray-600 mb-6">
            Explore our comprehensive documentation to get the most out of Solace Agent Mesh:
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
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </a>
          </div>
        </div>

        <div className="p-6 bg-gradient-to-b from-solace-blue-light to-blue-50 rounded-lg text-center">
          <h3 className="text-lg font-medium text-solace-blue mb-2">Connect with the Community</h3>
          <p className="text-gray-600 mb-4">
            Solace Agent Mesh is open source! We welcome contributions and discussions from the community.
          </p>

          {/* Container for GitHub and Forum link cards */}
          <div className="mt-6 flex flex-col sm:flex-row justify-center items-stretch gap-4">

            {/* GitHub Link Card */}
            <a
              href="https://github.com/SolaceLabs/solace-agent-mesh"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-1/2 p-4 rounded-md bg-white text-solace-blue border border-solace-blue hover:bg-solace-blue hover:text-white transition-colors flex flex-col items-center justify-center group"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" className="mb-2 text-solace-blue group-hover:text-white transition-colors">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
                fill="currentColor"/>
              </svg>
              <span className="font-medium">GitHub Repository</span>
            </a>

            {/* Solace Community Forum Link Card */}
            <a
              href="https://solace.community/c/solace-agent-mesh/16"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-1/2 p-4 rounded-md bg-white text-solace-blue border border-solace-blue hover:bg-solace-blue hover:text-white transition-colors flex flex-col items-center justify-center group"
            >
              <img
                src="Solace_community_logo.png"
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
      {/* Success banner */}
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
            Solace Agent Mesh Initialized Successfully!
          </h2>
          <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
            Your configuration has been saved and your project has been set up. You're now ready to start exploring the capabilities of Solace Agent Mesh.
          </p>
          <div className="inline-flex items-center px-4 py-2 bg-solace-blue text-white rounded-full shadow-sm">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clipRule="evenodd" />
            </svg>
            Configuration saved successfully
          </div>
        </div>
        {/* Decorative background elements */}
        <div className="absolute top-0 right-0 -mt-10 -mr-10 h-40 w-40 bg-green-200 opacity-50 rounded-full"></div>
        <div className="absolute bottom-0 left-0 -mb-10 -ml-10 h-32 w-32 bg-green-200 opacity-50 rounded-full"></div>
      </div>
      
      {/* Tabs navigation with page indicators */}
      <div className="flex items-center mb-6 border-b">
        <div className="flex-1 flex">
          <button
            onClick={() => setActiveTab('getting-started')}
            className={getTabButtonClass('getting-started')}
          >
            Getting Started
          </button>
          <button
            onClick={() => setActiveTab('tutorials')}
            className={getTabButtonClass('tutorials')}
          >
            Tutorials
          </button>
          <button
            onClick={() => setActiveTab('documentation')}
            className={getTabButtonClass('documentation')}
          >
            Documentation
          </button>
        </div>
        {/* Page indicator */}
        <div className="text-gray-500 text-sm mr-4 flex items-center">
          Page {currentTabIndex + 1} of {tabCount}
        </div>
      </div>
      
      {/* Content based on active tab */}
      {renderTabContent()}
      
      {/* Navigation buttons */}
      <div className="mt-8 flex justify-between items-center">
        <div className="text-sm text-gray-500">
          {/* Page indicator text for mobile */}
          <span className="md:hidden">Page {currentTabIndex + 1} of {tabCount}</span>
        </div>
        <div className="flex space-x-4">
          <Button 
            onClick={goToPreviousTab}
            variant="outline"
            type="button"
            disabled={currentTabIndex === 0}
          >
            Previous
          </Button>
          <Button 
            onClick={goToNextTab}
            type="button"
            disabled={currentTabIndex === tabCount - 1}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}