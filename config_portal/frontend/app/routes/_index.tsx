import type { MetaFunction } from "@remix-run/node";
import InitializationFlow from "../components/InitializationFlow";

export const meta: MetaFunction = () => {
  return [
    { title: "Solace Agent Mesh Initializer" },
    { name: "description", content: "Initialize your Solace Agent Mesh project" },
  ];
};

export default function Index() {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <InitializationFlow />
    </div>
  );
}