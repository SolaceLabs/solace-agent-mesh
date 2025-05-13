import { useState, useEffect } from "react";
import { useAgentRegistrations } from "./useAgentRegistrations";

const CapabilitiesPage = () => {
  const { agents, filteredAgents, searchFilter, setSearchFilter } =
    useAgentRegistrations();

  const [selectedAgent, setSelectedAgent] = useState(null);

  useEffect(() => {
    if (Object.keys(agents).length > 0 && !selectedAgent) {
      // Auto-select the first agent when agents are loaded
      setSelectedAgent(agents[Object.keys(agents)[0]]);
    }
  }, [agents, selectedAgent]);

  const handleAgentClick = (agentName) => {
    setSelectedAgent(agents[agentName]);
  };

  return (
    <div className="capabilities-page">
      <div className="page-header">
        <h2>Solace Agent Mesh Agents</h2>
        <input
          type="text"
          placeholder="Search agents..."
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          className="search-input"
        />
      </div>
      <div className="capabilities-content">
        <div className="agent-grid">
          {Object.entries(filteredAgents).length === 0 ? (
            <p className="no-agents">
              No agents registered yet. They will appear here as they register.
            </p>
          ) : (
            Object.entries(filteredAgents).map(([name, agent]) => (
              <div
                key={name}
                className={`agent-card ${
                  selectedAgent?.agent_name === name ? "selected" : ""
                }`}
                onClick={() => handleAgentClick(name)}
              >
                <h3>{name}</h3>
                <p>{agent.description || "No description available"}</p>
                <div className="agent-card-footer">
                  <div className="actions-count">
                    <span>{(agent.actions || []).length} actions</span>
                  </div>
                  <div className="actions-preview">
                    {(agent.actions || []).slice(0, 300).map(
                      (action, index) =>
                        action && (
                          <span key={index} className="action-name-preview">
                            {Object.keys(action)[0]}
                          </span>
                        )
                    )}
                    {/* {(agent.actions || []).length > 3 && (
                      <span className="more-actions">more...</span>
                    )} */}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
        {selectedAgent && (
          <div className="agent-details">
            <h2>{selectedAgent.agent_name}</h2>
            <p className="agent-description">
              {selectedAgent.description || "No description available"}
            </p>
            <div className="actions-list">
              <h3>Actions</h3>
              {(selectedAgent.actions || []).map((action) => {
                const actionName = Object.keys(action)[0];
                const actionDetails = action[actionName];
                return (
                  <details key={actionName} className="action-details">
                    <summary>{actionName}</summary>
                    <div className="action-content">
                      <p>{actionDetails.desc}</p>
                      <h4>Parameters:</h4>
                      <ul>
                        {actionDetails.params.map((param, paramIndex) => (
                          <li key={paramIndex}>
                            {typeof param === "object"
                              ? JSON.stringify(param)
                              : param}
                          </li>
                        ))}
                      </ul>
                      {actionDetails.examples.length > 0 && (
                        <>
                          <h4>Examples:</h4>
                          <ul>
                            {actionDetails.examples.map(
                              (example, exampleIndex) => (
                                <li key={exampleIndex}>
                                  {typeof example === "object"
                                    ? JSON.stringify(example)
                                    : example}
                                </li>
                              )
                            )}
                          </ul>
                        </>
                      )}
                      <h4>Required Scopes:</h4>
                      <ul className="scopes-list">
                        {actionDetails.required_scopes.map(
                          (scope, scopeIndex) => (
                            <li key={scopeIndex}>
                              {typeof scope === "object"
                                ? JSON.stringify(scope)
                                : scope}
                            </li>
                          )
                        )}
                      </ul>
                    </div>
                  </details>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CapabilitiesPage;
