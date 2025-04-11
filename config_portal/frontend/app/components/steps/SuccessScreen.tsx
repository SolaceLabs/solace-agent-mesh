export default function SuccessScreen() {
    return (
      <>
        <div className="p-6 bg-green-50 rounded-md mb-4 text-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-16 w-16 mx-auto text-green-500 mb-4"
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
          <h3 className="text-xl font-bold text-green-800 mb-2">
            Solace Agent Mesh Initialized Successfully!
          </h3>
          <p className="text-green-700">
            Your configuration has been saved and your project has been set
            up.
          </p>
        </div>
        <div className="p-4 bg-solace-blue text-white rounded-md">
          <h3 className="font-bold mb-2">Next Steps</h3>
          <p className="mb-4">
            Your configurations have been saved in the <code className="bg-gray-800 px-1 py-0.5 rounded">.env</code> file 
            in the root of the project and the <code className="bg-gray-800 px-1 py-0.5 rounded">solace-agent-mesh.yaml</code> file.
          </p>
          <p className="mb-4">
            To start Solace Agent Mesh directly, you can run:
          </p>
          <div className="bg-gray-800 text-gray-200 p-3 rounded font-mono text-sm mb-4">
            $ solace-agent-mesh run -b
          </div>
          <p className="mb-4">
            To get started adding components, use the{' '}
            <code className="bg-gray-800 px-1 py-0.5 rounded">
              solace-agent-mesh add
            </code>{' '}
            command to add agents and gateways.
          </p>
          <div className="bg-gray-800 text-gray-200 p-3 rounded font-mono text-sm mb-4">
            $ solace-agent-mesh add agent my-agent
          </div>
          <p className="mb-4 bg-gray-700 p-3 rounded text-yellow-300">
            <span className="font-bold">Pro Tip:</span> You can use <code className="bg-gray-800 px-1 py-0.5 rounded">sam</code> as a shorthand for <code className="bg-gray-800 px-1 py-0.5 rounded">solace-agent-mesh</code> in all commands:
          </p>
          <div className="bg-gray-800 text-gray-200 p-3 rounded font-mono text-sm">
            $ sam add agent my-agent
          </div>
        </div>
        <div className="p-4 bg-solace-blue text-white rounded-md mt-6">
          <h3 className="font-bold mb-2">Documentation Resources</h3>
          <p className="mb-4">
            For more information on how to use Solace Agent Mesh, check out our documentation:
          </p>
          <a 
            href="https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/" 
            className="inline-block bg-white bg-opacity-20 px-4 py-2 rounded-md hover:bg-opacity-30 transition-all font-medium"
          >
            View Documentation →
          </a>
        </div>
      </>
    );
  }