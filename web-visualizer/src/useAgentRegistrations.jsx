import {
  createContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useContext,
} from "react";
import PropTypes from "prop-types";

// Constants for agent registration management
const AGENT_TIMEOUT = 120000; // 2 minutes in milliseconds
const CLEANUP_INTERVAL = 30000; // 30 seconds

// Create context for agent registrations
const AgentRegistrationsContext = createContext(null);

// Context provider component for agent registrations
export const AgentRegistrationsProvider = ({ children }) => {
  // State for storing agent registrations and search filter
  const [registrations, setRegistrations] = useState({});
  const [searchFilter, setSearchFilter] = useState("");

  // Handler for new agent registrations
  const handleRegistration = useCallback((registration) => {
    if (!registration?.agent_name) {
      console.warn("Invalid registration message received:", registration);
      return;
    }

    const agentName = registration.agent_name;

    // Loop through the actions and remove any empty ones
    if (registration.actions) {
      registration.actions = registration.actions.filter((action) => action);
    }

    setRegistrations((prev) => ({
      ...prev,
      [agentName]: {
        ...registration,
        lastUpdate: Date.now(),
      },
    }));
  }, []);

  // Effect for setting up registration event listener
  useEffect(() => {
    const handleRegistrationEvent = (event) => {
      handleRegistration(event.detail);
    };

    window.addEventListener("agentRegistration", handleRegistrationEvent);
    return () =>
      window.removeEventListener("agentRegistration", handleRegistrationEvent);
  }, [handleRegistration]);

  // Effect for cleaning up stale agent registrations
  useEffect(() => {
    const cleanup = setInterval(() => {
      const now = Date.now();
      setRegistrations((prev) => {
        const updated = { ...prev };
        let hasChanges = false;

        Object.entries(updated).forEach(([name, agent]) => {
          if (now - agent.lastUpdate > AGENT_TIMEOUT) {
            delete updated[name];
            hasChanges = true;
          }
        });

        return hasChanges ? updated : prev;
      });
    }, CLEANUP_INTERVAL);

    return () => clearInterval(cleanup);
  }, []);

  // Memoized filtered agents based on search term
  const filteredAgents = useMemo(() => {
    const searchTerm = searchFilter.toLowerCase();
    return Object.fromEntries(
      Object.entries(registrations).filter(([name, agent]) => {
        return (
          name.toLowerCase().includes(searchTerm) ||
          (typeof agent.description === "string" &&
            agent.description.toLowerCase().includes(searchTerm)) ||
          agent.actions?.some((action) => {
            if (!action) return false;
            const actionKey = Object.keys(action)[0];
            const actionValue = action[actionKey];
            return (
              actionKey.toLowerCase().includes(searchTerm) ||
              (typeof actionValue?.desc === "string" &&
                actionValue.desc.toLowerCase().includes(searchTerm))
            );
          })
        );
      })
    );
  }, [registrations, searchFilter]);

  // Context value
  const value = {
    agents: registrations,
    filteredAgents,
    handleRegistration,
    searchFilter,
    setSearchFilter,
  };

  return (
    <AgentRegistrationsContext.Provider value={value}>
      {children}
    </AgentRegistrationsContext.Provider>
  );
};

AgentRegistrationsProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

// Custom hook for accessing agent registrations context
export const useAgentRegistrations = () => {
  const context = useContext(AgentRegistrationsContext);
  if (!context) {
    throw new Error(
      "useAgentRegistrations must be used within an AgentRegistrationsProvider"
    );
  }
  return context;
};
