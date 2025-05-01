// app/routes/install-agent.tsx
import type { MetaFunction } from "@remix-run/node";
import AgentInstallationFlow from "../components/AgentInstallation/AgentInstallationFlow";

export const meta: MetaFunction = () => {
  return [
    { title: "Install Agent - Solace Agent Mesh" },
    { name: "description", content: "Install a new agent for your Solace Agent Mesh project" },
  ];
};

export default function InstallAgentPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <AgentInstallationFlow />
    </div>
  );
}