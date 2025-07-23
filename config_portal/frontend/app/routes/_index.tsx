import type { MetaFunction } from "@remix-run/node";
import { useState, useEffect } from "react";
import { useSearchParams } from "@remix-run/react";
import InitializationFlow from "../components/InitializationFlow";
import AddAgentFlow from "../components/AddAgentFlow";
import PluginCatalogFlow from "../components/PluginCatalogFlow/PluginCatalogFlow";
import AddGatewayFlow from "../components/AddGatewayFlow";

export const meta: MetaFunction = () => {
  return [
    { title: "Solace Agent Mesh - Config Portal" },
    { name: "description", content: "Initialize your Solace Agent Mesh project or add new components." },
  ];
};

type ActiveFlow = "initialize" | "addAgent" | "pluginCatalog" | "addGateway";

export default function Index() {
  const [activeFlow, setActiveFlow] = useState<ActiveFlow>("initialize");
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const configMode = searchParams.get("config_mode");
    if (configMode === "addAgent") {
      setActiveFlow("addAgent");
    } else if (configMode === "pluginCatalog") {
      setActiveFlow("pluginCatalog");
    } else if (configMode === "addGateway") {
      setActiveFlow("addGateway");
    } else {
      setActiveFlow("initialize");
    }
  }, [searchParams]);

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold text-solace-purple">Solace Agent Mesh Configuration Portal</h1>
        </div>

        <div className="bg-white shadow-xl rounded-lg p-6 md:p-8 min-h-[500px]">
          {activeFlow === "initialize" && <InitializationFlow />}
          {activeFlow === "addAgent" && <AddAgentFlow />}
          {activeFlow === "pluginCatalog" && <PluginCatalogFlow />}
          {activeFlow === "addGateway" && <AddGatewayFlow />}
        </div>
        
        <footer className="mt-12 text-center text-sm text-gray-500">
          <p>&copy; {new Date().getFullYear()} Solace Agent Mesh. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
}