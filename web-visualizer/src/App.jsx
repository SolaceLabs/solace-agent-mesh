import { useState, useEffect } from "react";
import { AgentRegistrationsProvider } from "./useAgentRegistrations";
import {
  BrowserRouter as Router,
  Route,
  Routes,
  NavLink,
} from "react-router-dom";
import "./App.css";
import StimuliPage from "./StimuliPage";
import CapabilitiesPage from "./CapabilitiesPage";
import ConfigDialog from "./ConfigDialog";
import ConnectionSelector from "./ConnectionSelector";
import useSolaceConnection from "./useSolaceConnection";
import { storeInIndexedDB, getFromIndexedDB } from "./IndexedDBManager";

const LOCAL_STORAGE_KEY = "web-visualizer-config";
const SAVED_CONFIGS_KEY = "saved-configs";

const App = () => {
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showConnectionSelector, setShowConnectionSelector] = useState(false);
  const [isNewConfig, setIsNewConfig] = useState(false);
  const [savedConfigs, setSavedConfigs] = useState([]);

  const [config, setConfig] = useState(() => {
    try {
      const config = JSON.parse(
        localStorage.getItem(LOCAL_STORAGE_KEY) || "{}"
      );
      if (
        !config ||
        !config.connectionType ||
        !config.url ||
        !config.vpnName ||
        !config.userName
      ) {
        return {
          connectionType: "solace",
          url: window.config?.url ?? "ws://localhost:8008",
          vpnName: window.config?.vpn ?? "default",
          userName: window.config?.username ?? "default",
          password: window.config?.password ?? "default",
          namespace: window.config?.namespace ?? "",
        };
      }
      return config;
    } catch (error) {
      console.error("Error getting config from local storage:", error.message);
      return {
        connectionType: "solace",
        url: window.config?.url ?? "ws://localhost:8008",
        vpnName: window.config?.vpn ?? "default",
        userName: window.config?.username ?? "default",
        password: window.config?.password ?? "default",
        namespace: window.config?.namespace ?? "",
      };
    }
  });

  const [connect, disconnect, isConnected, setIsConnected] =
    useSolaceConnection((message) => {
      // Handle registration messages globally
      if (message.type === "registration") {
        const event = new CustomEvent("agentRegistration", {
          detail: message.content,
        });
        window.dispatchEvent(event);
        return; // Don't store registration messages in IndexedDB
      }

      // Store all messages in IndexedDB regardless of current page
      if (message.type === "stimulus") {
        storeInIndexedDB({
          ...message,
          responses: [],
        });
      } else if (
        [
          "response",
          "streamingResponse",
          "responseComplete",
          "actionRequest",
          "actionResponse",
          "orchestratorReinvoke",
          "llmServiceRequest",
          "llmServiceResponse",
        ].includes(message.type)
      ) {
        // Drop OrchestratorReinvoke messages
        if (message.type === "orchestratorReinvoke") {
          return;
        }
        console.log("EDE Processing message:", message);
        if (
          message.type === "llmServiceResponse" &&
          !message.content.last_chunk
        ) {
          return;
        }
        // For responses, we need to get the existing stimulus and update it
        if (
          message.type !== "streamingResponse" ||
          message.content.last_chunk
        ) {
          // Only update the database if this is the last chunk of a streaming response
          getFromIndexedDB().then((stimuli) => {
            const key = message.stimulus_uuid?._value || message.stimulus_uuid;
            const stimulus = stimuli[key];
            if (stimulus) {
              storeInIndexedDB({
                ...stimulus,
                responses: [message],
              });
            } else {
              return;
            }
          });
        }
      }

      // Also dispatch event for real-time updates if we're on the stimuli page
      const stimuliPage = document.querySelector(".stimuli-page");
      if (stimuliPage) {
        const event = new CustomEvent("newMessage", { detail: message });
        stimuliPage.dispatchEvent(event);
      }
    });

  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(config));
    } catch (error) {
      console.error("Error saving config to local storage:", error.message);
    }
  }, [config]);

  useEffect(() => {
    const loadedConfigs = JSON.parse(
      localStorage.getItem(SAVED_CONFIGS_KEY) || "[]"
    );
    setSavedConfigs(loadedConfigs);
  }, []);

  const onDialogClose = (proceed) => {
    if (proceed) {
      // Format the namespace before connecting
      const formattedConfig = {
        ...config,
        namespace: config.namespace && !config.namespace.endsWith('/') 
          ? config.namespace + '/' 
          : config.namespace
      };
      // Update the config state with the formatted namespace
      setConfig(formattedConfig);
      
      connect(formattedConfig)
        .then(() => {
          setIsConnected(true);
          if (formattedConfig.name) {
            const existingConfigIndex = savedConfigs.findIndex(
              (c) => c.name === formattedConfig.name
            );
            let updatedConfigs;
            if (existingConfigIndex !== -1) {
              // Replace existing config
              updatedConfigs = [...savedConfigs];
              updatedConfigs[existingConfigIndex] = formattedConfig;
            } else {
              // Add new config
              updatedConfigs = [...savedConfigs, formattedConfig];
            }
            setSavedConfigs(updatedConfigs);
            localStorage.setItem(
              SAVED_CONFIGS_KEY,
              JSON.stringify(updatedConfigs)
            );
          }
        })
        .catch((error) => {
          console.error("Connection failed:", error);
          setIsConnected(false);
        });
    }
    setShowConfigDialog(false);
    setIsNewConfig(false);
  };

  const handleDisconnect = () => {
    disconnect();
    setIsConnected(false);
  };

  const handleConnectionSelect = (selectedConfig, shouldConnect = false) => {
    setConfig(selectedConfig);
    setShowConnectionSelector(false);
    if (shouldConnect) {
      connect(selectedConfig)
        .then(() => {
          setIsConnected(true);
        })
        .catch((error) => {
          console.error("Connection failed:", error);
          setIsConnected(false);
        });
    } else {
      setShowConfigDialog(true);
      setIsNewConfig(false);
    }
  };

  const handleCreateNew = () => {
    setConfig({
      name: "",
      connectionType: "solace",
      url: window.config?.url ?? "ws://localhost:8008",
      vpnName: window.config?.vpn ?? "default",
      userName: window.config?.username ?? "default",
      password: window.config?.password ?? "default",
      namespace: window.config?.namespace ?? "",
    });
    setShowConnectionSelector(false);
    setShowConfigDialog(true);
    setIsNewConfig(true);
  };

  const handleEditConnection = (configToEdit) => {
    setConfig(configToEdit);
    setShowConnectionSelector(false);
    setShowConfigDialog(true);
    setIsNewConfig(false);
  };

  const handleDeleteConnection = (configName) => {
    const updatedConfigs = savedConfigs.filter(
      (config) => config.name !== configName
    );
    setSavedConfigs(updatedConfigs);
    localStorage.setItem(SAVED_CONFIGS_KEY, JSON.stringify(updatedConfigs));
    setShowConnectionSelector(false);
  };

  return (
    <Router>
      <AgentRegistrationsProvider>
        <div className="app-wrapper">
          <div className="app-container">
            <header className="header">
              <nav className="top-menu">
                <h1 className="app-title">Solace Agent Mesh Visualizer</h1>
                <ul className="nav-links">
                  <li>
                    <NavLink to="/" end>
                      Stimuli
                    </NavLink>
                  </li>
                  <li>
                    <NavLink to="/capabilities">Agents</NavLink>
                  </li>
                </ul>
                <div className="connection-controls">
                  {showConnectionSelector && (
                    <ConnectionSelector
                      onSelect={handleConnectionSelect}
                      onCreateNew={handleCreateNew}
                      onCancel={() => setShowConnectionSelector(false)}
                      onEdit={handleEditConnection}
                      onDelete={handleDeleteConnection}
                    />
                  )}
                  <ConfigDialog
                    open={!isConnected && showConfigDialog}
                    config={config}
                    setConfig={setConfig}
                    onClose={onDialogClose}
                    isNewConfig={isNewConfig}
                    savedConfigs={savedConfigs}
                  />
                  <button
                    className="button button-info"
                    onClick={
                      isConnected
                        ? handleDisconnect
                        : () => setShowConnectionSelector(true)
                    }
                  >
                    {isConnected ? "Disconnect" : "Connect"}
                  </button>
                </div>
              </nav>
            </header>
            <Routes>
              <Route path="/" element={<StimuliPage />} />
              <Route path="/capabilities" element={<CapabilitiesPage />} />
            </Routes>
          </div>
        </div>
      </AgentRegistrationsProvider>
    </Router>
  );
};

export default App;
