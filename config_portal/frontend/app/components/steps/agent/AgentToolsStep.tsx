import React, { useState } from "react";
import { StepProps } from "../../AddAgentFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Select from "../../ui/Select";
import Button from "../../ui/Button";
import Modal from "../../ui/Modal";
import { InfoBox } from "../../ui/InfoBoxes";
import ChipInput from "../../ui/ChipInput";
import AutocompleteInput from "../../ui/AutocompleteInput";
import KeyValueInput from "../../ui/KeyValueInput";
import ListInput from "../../ui/ListInput";

export interface Tool {
  id?: string;
  tool_type: "python" | "mcp" | "builtin" | "builtin-group" | "";
  tool_name?: string;
  tool_description?: string;
  group_name?: string;
  component_module?: string;
  function_name?: string;
  component_base_path?: string;

  // Structured versions for UI
  environment_variables_ui?: Record<string, string>;
  tool_config_ui?: Record<string, string>;

  connection_params?: Record<string, unknown>;
  environment_variables?: Record<string, unknown>;
  required_scopes?: string[];
  tool_config?: Record<string, unknown>;

  // MCP transport-specific fields
  transport_type?: "stdio" | "sse" | "streamable-http" | "";
  // stdio fields
  stdio_command?: string;
  stdio_args?: string[];
  stdio_env?: Record<string, string>;
  // sse fields
  sse_url?: string;
  sse_headers?: Record<string, string>;
  // streamable-http fields
  streamable_http_url?: string;
  streamable_http_headers?: Record<string, string>;

  // MCP timeout field (applies to all transports)
  mcp_timeout?: number;

  // MCP auth fields
  auth_type?: "none" | "api_key" | "bearer" | "oauth2" | "";
  // api_key / bearer fields
  auth_token?: string;
  auth_header_name?: string; // For api_key (e.g., "X-API-Key")
  // oauth2 fields
  oauth2_client_id?: string;
  oauth2_client_secret?: string;
  oauth2_authorization_url?: string;
  oauth2_token_url?: string;
  oauth2_scopes?: string[];
}

const initialToolState: Tool = {
  id: undefined,
  tool_type: "",
  tool_name: "",
  tool_description: "",
  group_name: "",
  component_module: "",
  function_name: "",
  component_base_path: "",
  connection_params: undefined,
  environment_variables: undefined,
  required_scopes: [],
  tool_config: undefined,
  environment_variables_ui: {},
  tool_config_ui: {},
  transport_type: "",
  stdio_command: "",
  stdio_args: [],
  stdio_env: {},
  sse_url: "",
  sse_headers: {},
  streamable_http_url: "",
  streamable_http_headers: {},
  mcp_timeout: 30,
  auth_type: "",
  auth_token: "",
  auth_header_name: "Authorization",
  oauth2_client_id: "",
  oauth2_client_secret: "",
  oauth2_authorization_url: "",
  oauth2_token_url: "",
  oauth2_scopes: [],
};



const AgentToolsStep: React.FC<StepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
  availableTools,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentTool, setCurrentTool] = useState<Tool>(initialToolState);
  const [modalView, setModalView] = useState<
    "initial" | "builtin-group" | "builtin-tool" | "custom"
  >("initial");
  const [editingToolId, setEditingToolId] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<
    Partial<Record<keyof Tool, string>>
  >({});

  const toolsList: Tool[] = Array.isArray(data.tools) ? data.tools : [];

  const openModalForNew = () => {
    setCurrentTool({ ...initialToolState, id: Date.now().toString() });
    setEditingToolId(null);
    setFormErrors({});
    setModalView("initial");
    setIsModalOpen(true);
  };

  const openModalForEdit = (tool: Tool) => {
    if (tool.tool_type === "builtin-group") {
      setModalView("builtin-group");
    } else if (tool.tool_type === "builtin") {
      setModalView("builtin-tool");
    } else {
      setModalView("custom");
    }

    // Extract transport-specific fields from connection_params for MCP tools
    // Also extract UI-friendly versions of environment_variables and tool_config
    let transportFields: Partial<Tool> = {};

    // Convert environment_variables and tool_config to UI format
    const envVarsUI: Record<string, string> = {};
    if (tool.environment_variables && typeof tool.environment_variables === "object") {
      Object.entries(tool.environment_variables).forEach(([key, value]) => {
        envVarsUI[key] = String(value);
      });
    }

    const toolConfigUI: Record<string, string> = {};
    if (tool.tool_config && typeof tool.tool_config === "object") {
      Object.entries(tool.tool_config).forEach(([key, value]) => {
        toolConfigUI[key] = String(value);
      });
    }

    if (tool.tool_type === "mcp" && tool.connection_params) {
      const cp = tool.connection_params;
      const type = cp.type as string;

      if (type === "stdio") {
        transportFields = {
          transport_type: "stdio",
          stdio_command: cp.command as string || "",
          stdio_args: Array.isArray(cp.args) ? cp.args as string[] : [],
          stdio_env: (cp.env && typeof cp.env === "object") ? cp.env as Record<string, string> : {},
          mcp_timeout: (cp.timeout as number) || 30,
        };
      } else if (type === "sse") {
        transportFields = {
          transport_type: "sse",
          sse_url: cp.url as string || "",
          sse_headers: (cp.headers && typeof cp.headers === "object") ? cp.headers as Record<string, string> : {},
          mcp_timeout: (cp.timeout as number) || 30,
        };
      } else if (type === "streamable-http") {
        transportFields = {
          transport_type: "streamable-http",
          streamable_http_url: cp.url as string || "",
          streamable_http_headers: (cp.headers && typeof cp.headers === "object") ? cp.headers as Record<string, string> : {},
          mcp_timeout: (cp.timeout as number) || 30,
        };
      }
    }

    // Extract auth fields if present
    if (tool.tool_type === "mcp" && (tool as unknown as Record<string, unknown>).auth) {
      const auth = (tool as unknown as Record<string, unknown>).auth as Record<string, unknown>;
      const authType = auth.type as string;

      if (authType === "api_key") {
        transportFields.auth_type = "api_key";
        transportFields.auth_token = (auth.apiKey || auth.token || "") as string;
        transportFields.auth_header_name = (auth.headerName || "X-API-Key") as string;
      } else if (authType === "bearer") {
        transportFields.auth_type = "bearer";
        transportFields.auth_token = (auth.token || "") as string;
      } else if (authType === "oauth2") {
        transportFields.auth_type = "oauth2";
        if (auth.credential && typeof auth.credential === "object") {
          const credential = auth.credential as Record<string, unknown>;
          transportFields.oauth2_client_id = (credential.client_id || "") as string;
          transportFields.oauth2_client_secret = (credential.client_secret || "") as string;
        }
        if (auth.scheme && typeof auth.scheme === "object") {
          const scheme = auth.scheme as Record<string, unknown>;
          transportFields.oauth2_authorization_url = (scheme.authorization_url || "") as string;
          transportFields.oauth2_token_url = (scheme.token_url || "") as string;
          transportFields.oauth2_scopes = Array.isArray(scheme.scopes) ? scheme.scopes as string[] : [];
        }
      }
    }

    const toolForEdit: Tool = {
      ...initialToolState,
      ...tool,
      ...transportFields,
      id: tool.id || Date.now().toString(),
      tool_type: tool.tool_type || "",
      required_scopes: Array.isArray(tool.required_scopes)
        ? tool.required_scopes
        : [],
      environment_variables_ui: envVarsUI,
      tool_config_ui: toolConfigUI,
    };
    setCurrentTool(toolForEdit);
    setEditingToolId(tool.id || null);
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleModalChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) => {
    const { name, value } = e.target;

    // Handle number fields
    if (name === "mcp_timeout") {
      const numValue = value === "" ? 30 : parseInt(value, 10);
      setCurrentTool((prev) => ({ ...prev, [name]: numValue }));
    } else {
      setCurrentTool((prev) => ({ ...prev, [name]: value }));
    }
  };

  const handleChipInputChange = (fieldName: keyof Tool, values: string[]) => {
    setCurrentTool((prev) => ({ ...prev, [fieldName]: values }));
  };

  const handleListInputChange = (fieldName: keyof Tool, values: string[]) => {
    setCurrentTool((prev) => ({ ...prev, [fieldName]: values }));
  };

  const handleKeyValueInputChange = (fieldName: keyof Tool, values: Record<string, string>) => {
    setCurrentTool((prev) => ({ ...prev, [fieldName]: values }));
  };

  const validateToolForm = (): boolean => {
    const errors: Partial<Record<keyof Tool, string>> = {};
    if (!currentTool.tool_type) errors.tool_type = "Tool type is required.";

    if (currentTool.tool_type === "builtin-group") {
      if (!currentTool.group_name)
        errors.group_name = "Group name is required.";
    } else if (currentTool.tool_type === "builtin") {
      if (!currentTool.tool_name) errors.tool_name = "Tool name is required.";
    } else if (currentTool.tool_type === "python") {
      if (!currentTool.component_module)
        errors.component_module = "Component module is required.";
      if (!currentTool.function_name)
        errors.function_name = "Function name is required.";
    } else if (currentTool.tool_type === "mcp") {
      if (!currentTool.transport_type) {
        errors.transport_type = "Transport type is required for MCP tools.";
      } else if (currentTool.transport_type === "stdio") {
        if (!currentTool.stdio_command)
          errors.stdio_command = "Command is required for stdio transport.";
      } else if (currentTool.transport_type === "sse") {
        if (!currentTool.sse_url)
          errors.sse_url = "URL is required for SSE transport.";
      } else if (currentTool.transport_type === "streamable-http") {
        if (!currentTool.streamable_http_url)
          errors.streamable_http_url = "URL is required for streamable-http transport.";
      }

      // Validate auth fields
      if (currentTool.auth_type === "api_key") {
        if (!currentTool.auth_header_name)
          errors.auth_header_name = "Header name is required for API key authentication.";
        if (!currentTool.auth_token)
          errors.auth_token = "API key is required for API key authentication.";
      } else if (currentTool.auth_type === "bearer") {
        if (!currentTool.auth_token)
          errors.auth_token = "Bearer token is required for bearer authentication.";
      } else if (currentTool.auth_type === "oauth2") {
        if (!currentTool.oauth2_client_id)
          errors.oauth2_client_id = "Client ID is required for OAuth2 authentication.";
        if (!currentTool.oauth2_client_secret)
          errors.oauth2_client_secret = "Client secret is required for OAuth2 authentication.";
      }
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSaveTool = () => {
    if (!validateToolForm()) return;

    const baseTool = {
      id: currentTool.id || Date.now().toString(),
      tool_type: currentTool.tool_type,
    };

    let processedTool: Tool;

    switch (currentTool.tool_type) {
      case "builtin-group":
        processedTool = { ...baseTool, group_name: currentTool.group_name };
        break;
      case "builtin":
        processedTool = { ...baseTool, tool_name: currentTool.tool_name };
        break;
      case "python":
        processedTool = {
          ...baseTool,
          tool_name: currentTool.tool_name || undefined,
          tool_description: currentTool.tool_description || undefined,
          component_module: currentTool.component_module || undefined,
          function_name: currentTool.function_name || undefined,
          component_base_path: currentTool.component_base_path || undefined,
          tool_config: currentTool.tool_config_ui && Object.keys(currentTool.tool_config_ui).length > 0
            ? currentTool.tool_config_ui
            : undefined,
          required_scopes: currentTool.required_scopes || [],
        };
        break;
      case "mcp": {
        // Build connection_params from transport-specific fields
        let connection_params: Record<string, unknown> = {};

        if (currentTool.transport_type === "stdio") {
          connection_params = {
            type: "stdio",
            command: currentTool.stdio_command,
            args: currentTool.stdio_args || [],
            timeout: currentTool.mcp_timeout || 30,
          };
          if (currentTool.stdio_env && Object.keys(currentTool.stdio_env).length > 0) {
            connection_params.env = currentTool.stdio_env;
          }
        } else if (currentTool.transport_type === "sse") {
          connection_params = {
            type: "sse",
            url: currentTool.sse_url,
            timeout: currentTool.mcp_timeout || 30,
          };
          if (currentTool.sse_headers && Object.keys(currentTool.sse_headers).length > 0) {
            connection_params.headers = currentTool.sse_headers;
          }
        } else if (currentTool.transport_type === "streamable-http") {
          connection_params = {
            type: "streamable-http",
            url: currentTool.streamable_http_url,
            timeout: currentTool.mcp_timeout || 30,
          };
          if (currentTool.streamable_http_headers && Object.keys(currentTool.streamable_http_headers).length > 0) {
            connection_params.headers = currentTool.streamable_http_headers;
          }
        }

        // Build auth object from UI fields
        let auth: Record<string, unknown> | undefined = undefined;
        if (currentTool.auth_type === "api_key") {
          auth = {
            type: "api_key",
            apiKey: currentTool.auth_token,
            headerName: currentTool.auth_header_name || "X-API-Key",
          };
        } else if (currentTool.auth_type === "bearer") {
          auth = {
            type: "bearer",
            token: currentTool.auth_token,
          };
        } else if (currentTool.auth_type === "oauth2") {
          auth = {
            type: "oauth2",
          };
          if (currentTool.oauth2_client_id || currentTool.oauth2_client_secret) {
            auth.credential = {
              auth_type: "oauth2",
              client_id: currentTool.oauth2_client_id,
              client_secret: currentTool.oauth2_client_secret,
            };
          }
          if (currentTool.oauth2_authorization_url || currentTool.oauth2_token_url || (currentTool.oauth2_scopes && currentTool.oauth2_scopes.length > 0)) {
            auth.scheme = {
              grant_type: "authorization_code",
              authorization_url: currentTool.oauth2_authorization_url,
              token_url: currentTool.oauth2_token_url,
              scopes: currentTool.oauth2_scopes || [],
            };
          }
        }

        // Build environment_variables and tool_config from UI fields
        const environment_variables = currentTool.environment_variables_ui && Object.keys(currentTool.environment_variables_ui).length > 0
          ? currentTool.environment_variables_ui
          : undefined;

        const tool_config = currentTool.tool_config_ui && Object.keys(currentTool.tool_config_ui).length > 0
          ? currentTool.tool_config_ui
          : undefined;

        processedTool = {
          ...baseTool,
          tool_name: currentTool.tool_name || undefined,
          connection_params,
          environment_variables,
          tool_config,
          required_scopes: currentTool.required_scopes || [],
        };

        // Add auth if configured
        if (auth) {
          (processedTool as unknown as Record<string, unknown>).auth = auth;
        }

        break;
      }
      default:
        setIsModalOpen(false);
        return;
    }

    let newToolsList: Tool[];
    if (editingToolId) {
      newToolsList = toolsList.map((t) =>
        t.id === editingToolId ? processedTool : t
      );
    } else {
      newToolsList = [...toolsList, processedTool];
    }

    // Auto-include web tool group for remote MCP transports
    if (
      processedTool.tool_type === "mcp" &&
      (currentTool.transport_type === "sse" || currentTool.transport_type === "streamable-http")
    ) {
      const hasWebTool = newToolsList.some(
        (t) =>
          (t.tool_type === "builtin-group" && t.group_name === "web") ||
          (t.tool_type === "builtin" && t.tool_name === "web_request")
      );

      if (!hasWebTool) {
        const webToolGroup: Tool = {
          id: `web_auto_${Date.now()}`,
          tool_type: "builtin-group",
          group_name: "web",
        };
        newToolsList.push(webToolGroup);
      }
    }

    updateData({ tools: newToolsList });
    setIsModalOpen(false);
    setEditingToolId(null);
  };

  const handleDeleteTool = (toolId?: string) => {
    if (!toolId) return;

    // Check if this is an auto-added web tool
    const toolToDelete = toolsList.find((t) => t.id === toolId);
    if (toolToDelete?.id?.startsWith("web_auto_")) {
      // Check if there are still remote MCP tools that need it
      const hasRemoteMcpTools = toolsList.some(
        (t) =>
          t.id !== toolId &&
          t.tool_type === "mcp" &&
          (t.transport_type === "sse" || t.transport_type === "streamable-http")
      );

      if (hasRemoteMcpTools) {
        alert(
          "Cannot delete the web tool group while remote MCP tools (SSE or streamable-http) are configured. " +
          "The web tool provides network access required by remote MCP servers."
        );
        return;
      }
    }

    updateData({ tools: toolsList.filter((t) => t.id !== toolId) });
  };

  const renderToolProperties = (tool: Tool) => {
    const props = [];
    if (tool.tool_type === "builtin-group") {
      props.push(`Group: ${tool.group_name}`);
    } else if (tool.tool_name) {
      props.push(`Name: ${tool.tool_name}`);
    } else if (tool.tool_type === "python" && tool.function_name) {
      props.push(`Func: ${tool.function_name}`);
    }

    if (tool.component_module) props.push(`Module: ${tool.component_module}`);
    return props.join(", ") || "No details";
  };

  return (
    <div className="space-y-6">
      <InfoBox>
        Define custom tools for your agent. Tools can be Python functions, MCP
        servers, or built-in ADK capabilities. The final tools configuration
        will be submitted as a list of tool objects.
      </InfoBox>
      <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4">
        Custom Tools
      </h3>

      <Button onClick={openModalForNew} variant="secondary">
        + Add Tool
      </Button>

      {toolsList.length > 0 ? (
        <div className="mt-4 space-y-3">
          <table className="min-w-full divide-y divide-gray-200 border">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Details
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {toolsList.map((tool, index) => (
                <tr key={tool.id || index}>
                  <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-700">
                    {tool.tool_type}
                    {tool.id?.startsWith("web_auto_") && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                        Auto-added
                      </span>
                    )}
                  </td>
                  <td
                    className="px-4 py-2 whitespace-nowrap text-sm text-gray-500 max-w-xs truncate"
                    title={renderToolProperties(tool)}
                  >
                    {renderToolProperties(tool)}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-sm space-x-2">
                    <Button
                      onClick={() => openModalForEdit(tool)}
                      variant="outline"
                    >
                      Edit
                    </Button>
                    <Button
                      onClick={() => handleDeleteTool(tool.id)}
                      variant="outline"
                      className="text-red-600 border-red-300 hover:bg-red-50"
                      disabled={
                        tool.id?.startsWith("web_auto_") &&
                        toolsList.some(
                          (t) =>
                            t.id !== tool.id &&
                            t.tool_type === "mcp" &&
                            (t.transport_type === "sse" || t.transport_type === "streamable-http")
                        )
                      }
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-500 mt-4">No tools configured yet.</p>
      )}

      {isModalOpen && (
        <Modal
          title={editingToolId ? "Edit Tool" : "Add New Tool"}
          onClose={() => setIsModalOpen(false)}
        >
          <div className="space-y-4 max-h-[70vh] overflow-y-auto p-1">
            {modalView === "initial" && (
              <div className="space-y-3">
                <p className="text-sm text-gray-600">
                  What kind of tool do you want to add?
                </p>
                <Button
                  onClick={() => {
                    setCurrentTool((prev) => ({
                      ...prev,
                      tool_type: "builtin-group",
                    }));
                    setModalView("builtin-group");
                  }}
                  variant="secondary"
                  className="w-full justify-start"
                >
                  Group of Built-in Tools
                </Button>
                <Button
                  onClick={() => {
                    setCurrentTool((prev) => ({
                      ...prev,
                      tool_type: "builtin",
                    }));
                    setModalView("builtin-tool");
                  }}
                  variant="secondary"
                  className="w-full justify-start"
                >
                  Single Built-in Tool
                </Button>
                <Button
                  onClick={() => {
                    setCurrentTool((prev) => ({
                      ...prev,
                      tool_type: "python",
                    }));
                    setModalView("custom");
                  }}
                  variant="secondary"
                  className="w-full justify-start"
                >
                  Python Tool
                </Button>
                <Button
                  onClick={() => {
                    setCurrentTool((prev) => ({ ...prev, tool_type: "mcp" }));
                    setModalView("custom");
                  }}
                  variant="secondary"
                  className="w-full justify-start"
                >
                  MCP Tool
                </Button>
              </div>
            )}

            {modalView === "builtin-group" && (
              <FormField
                label="Built-in Tool Group"
                htmlFor="group_name"
                error={formErrors.group_name}
                required
              >
                <Select
                  id="group_name"
                  name="group_name"
                  value={currentTool.group_name || ""}
                  onChange={handleModalChange}
                  options={[
                    { value: "", label: "Select a group..." },
                    ...(availableTools &&
                    "groups" in availableTools &&
                    availableTools.groups
                      ? Object.keys(availableTools.groups).map((key) => ({
                          value: key,
                          label: `${key
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (l) => l.toUpperCase())} - ${
                            (
                              availableTools as {
                                groups: Record<string, { description: string }>;
                              }
                            ).groups[key].description
                          }`,
                        }))
                      : []),
                  ]}
                />
              </FormField>
            )}

            {modalView === "builtin-tool" && (
              <FormField
                label="Built-in Tool Name"
                htmlFor="tool_name"
                error={formErrors.tool_name}
                required
              >
                <AutocompleteInput
                  id="tool_name"
                  name="tool_name"
                  value={currentTool.tool_name || ""}
                  onChange={handleModalChange}
                  suggestions={
                    availableTools &&
                    "tools" in availableTools &&
                    availableTools.tools
                      ? Object.keys(availableTools.tools)
                      : []
                  }
                  placeholder="Select a built-in tool..."
                />
              </FormField>
            )}

            {modalView === "custom" && (
              <>
                {currentTool.tool_type === "python" && (
                  <>
                    <FormField
                      label="Tool Name (Optional)"
                      htmlFor="tool_name"
                      error={formErrors.tool_name}
                      helpText="Optional: A descriptive name for this Python tool. Overwrites the python function name"
                    >
                      <Input
                        id="tool_name"
                        name="tool_name"
                        value={currentTool.tool_name || ""}
                        onChange={handleModalChange}
                      />
                    </FormField>
                    <FormField
                      label="Tool Description (Optional)"
                      htmlFor="tool_description"
                      error={formErrors.tool_description}
                      helpText="Optional: A brief description of what this tool does. Overwrites the python function docs"
                    >
                      <Input
                        id="tool_description"
                        name="tool_description"
                        value={currentTool.tool_description || ""}
                        onChange={handleModalChange}
                        placeholder="e.g., Fetch user profile data"
                      />
                    </FormField>
                    <FormField
                      label="Component Module"
                      htmlFor="component_module"
                      error={formErrors.component_module}
                      required
                    >
                      <Input
                        id="component_module"
                        name="component_module"
                        value={currentTool.component_module || ""}
                        onChange={handleModalChange}
                        placeholder="e.g., my_agent.custom_tools"
                      />
                    </FormField>
                    <FormField
                      label="Function Name"
                      htmlFor="function_name"
                      error={formErrors.function_name}
                      required
                    >
                      <Input
                        id="function_name"
                        name="function_name"
                        value={currentTool.function_name || ""}
                        onChange={handleModalChange}
                        placeholder="e.g., my_tool_function"
                      />
                    </FormField>
                    <FormField
                      label="Component Base Path (Optional)"
                      htmlFor="component_base_path"
                      error={formErrors.component_base_path}
                      helpText="Base path for module resolution if not in PYTHONPATH."
                    >
                      <Input
                        id="component_base_path"
                        name="component_base_path"
                        value={currentTool.component_base_path || ""}
                        onChange={handleModalChange}
                        placeholder="e.g., src/plugins"
                      />
                    </FormField>
                  </>
                )}

                {currentTool.tool_type === "mcp" && (
                  <>
                    <FormField
                      label="MCP Tool Name (Optional)"
                      htmlFor="tool_name"
                      error={formErrors.tool_name}
                      helpText="Name of the specific MCP tool (optional if using all tools from MCP server)"
                    >
                      <Input
                        id="tool_name"
                        name="tool_name"
                        value={currentTool.tool_name || ""}
                        onChange={handleModalChange}
                      />
                    </FormField>

                    <FormField
                      label="Transport Type"
                      htmlFor="transport_type"
                      error={formErrors.transport_type}
                      required
                    >
                      <Select
                        id="transport_type"
                        name="transport_type"
                        value={currentTool.transport_type || ""}
                        onChange={handleModalChange}
                        options={[
                          { value: "", label: "Select transport type..." },
                          { value: "stdio", label: "stdio - Standard Input/Output" },
                          { value: "sse", label: "sse - Server-Sent Events" },
                          { value: "streamable-http", label: "streamable-http - Streamable HTTP" },
                        ]}
                      />
                    </FormField>

                    {currentTool.transport_type === "stdio" && (
                      <>
                        <InfoBox>
                          <strong>Example stdio configuration:</strong>
                          <br />
                          Command: <code>npx</code>
                          <br />
                          Arguments (in order):
                          <br />
                          &nbsp;&nbsp;1. <code>-y</code>
                          <br />
                          &nbsp;&nbsp;2. <code>@modelcontextprotocol/server-filesystem</code>
                          <br />
                          &nbsp;&nbsp;3. <code>/path/to/allowed/directory</code>
                          <br />
                          <em>Do not include quotation marks when entering arguments.</em>
                        </InfoBox>
                        <FormField
                          label="Command"
                          htmlFor="stdio_command"
                          error={formErrors.stdio_command}
                          required
                          helpText="The command to execute (e.g., 'python', 'node', 'npx')"
                        >
                          <Input
                            id="stdio_command"
                            name="stdio_command"
                            value={currentTool.stdio_command || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., npx"
                          />
                        </FormField>
                        <ListInput
                          id="stdio_args"
                          label="Arguments"
                          values={currentTool.stdio_args || []}
                          onChange={(values) => handleListInputChange("stdio_args", values)}
                          error={formErrors.stdio_args}
                          helpText="Command line arguments in order. Enter each argument separately without quotes."
                          placeholder="No arguments added yet"
                          itemPlaceholder="e.g., -y or /path/to/directory"
                        />
                        <KeyValueInput
                          id="stdio_env"
                          label="Environment Variables (Optional)"
                          values={currentTool.stdio_env || {}}
                          onChange={(values) => handleKeyValueInputChange("stdio_env", values)}
                          error={formErrors.stdio_env}
                          helpText="Optional environment variables for the process"
                          placeholder="No environment variables added"
                          keyPlaceholder="Variable name (e.g., PATH)"
                          valuePlaceholder="Variable value (e.g., /usr/bin)"
                        />
                      </>
                    )}

                    {currentTool.transport_type === "sse" && (
                      <>
                        <InfoBox>
                          <strong>📡 Remote MCP Server</strong>
                          <br />
                          SSE transport connects to remote servers over HTTP. The <strong>web</strong> builtin tool group will be automatically included in your agent configuration to enable network access.
                        </InfoBox>
                        <FormField
                          label="URL"
                          htmlFor="sse_url"
                          error={formErrors.sse_url}
                          required
                          helpText="The SSE endpoint URL"
                        >
                          <Input
                            id="sse_url"
                            name="sse_url"
                            value={currentTool.sse_url || ""}
                            onChange={handleModalChange}
                            placeholder="https://mcp.example.com/v1/sse"
                          />
                        </FormField>
                        <KeyValueInput
                          id="sse_headers"
                          label="Headers (Optional)"
                          values={currentTool.sse_headers || {}}
                          onChange={(values) => handleKeyValueInputChange("sse_headers", values)}
                          error={formErrors.sse_headers}
                          helpText="Optional HTTP headers for authentication or configuration"
                          placeholder="No headers added"
                          keyPlaceholder="Header name (e.g., Authorization)"
                          valuePlaceholder="Header value (e.g., Bearer ${MCP_AUTH_TOKEN})"
                        />
                      </>
                    )}

                    {currentTool.transport_type === "streamable-http" && (
                      <>
                        <InfoBox>
                          <strong>📡 Remote MCP Server</strong>
                          <br />
                          Streamable HTTP transport connects to remote servers over HTTP. The <strong>web</strong> builtin tool group will be automatically included in your agent configuration to enable network access.
                        </InfoBox>
                        <FormField
                          label="URL"
                          htmlFor="streamable_http_url"
                          error={formErrors.streamable_http_url}
                          required
                          helpText="The streamable HTTP endpoint URL"
                        >
                          <Input
                            id="streamable_http_url"
                            name="streamable_http_url"
                            value={currentTool.streamable_http_url || ""}
                            onChange={handleModalChange}
                            placeholder="https://mcp.example.com:port/mcp/message"
                          />
                        </FormField>
                        <KeyValueInput
                          id="streamable_http_headers"
                          label="Headers (Optional)"
                          values={currentTool.streamable_http_headers || {}}
                          onChange={(values) => handleKeyValueInputChange("streamable_http_headers", values)}
                          error={formErrors.streamable_http_headers}
                          helpText="Optional HTTP headers for authentication or configuration"
                          placeholder="No headers added"
                          keyPlaceholder="Header name (e.g., Authorization)"
                          valuePlaceholder="Header value (e.g., Bearer ${MCP_AUTH_TOKEN})"
                        />
                      </>
                    )}

                    <KeyValueInput
                      id="environment_variables_ui"
                      label="Environment Variables (Optional)"
                      values={currentTool.environment_variables_ui || {}}
                      onChange={(values) => handleKeyValueInputChange("environment_variables_ui", values)}
                      error={formErrors.environment_variables_ui}
                      helpText="Global environment variables for the MCP connection"
                      placeholder="No environment variables added"
                      keyPlaceholder="Variable name"
                      valuePlaceholder="Variable value"
                    />

                    <FormField
                      label="Authentication Type (Optional)"
                      htmlFor="auth_type"
                      helpText="Configure authentication for the MCP server"
                    >
                      <Select
                        id="auth_type"
                        name="auth_type"
                        value={currentTool.auth_type || ""}
                        onChange={handleModalChange}
                        options={[
                          { value: "", label: "No authentication" },
                          { value: "api_key", label: "API Key" },
                          { value: "bearer", label: "Bearer Token" },
                          { value: "oauth2", label: "OAuth2" },
                        ]}
                      />
                    </FormField>

                    {currentTool.auth_type === "api_key" && (
                      <>
                        <FormField
                          label="Header Name"
                          htmlFor="auth_header_name"
                          required
                          error={formErrors.auth_header_name}
                          helpText="The HTTP header name for the API key"
                        >
                          <Input
                            id="auth_header_name"
                            name="auth_header_name"
                            value={currentTool.auth_header_name || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., X-API-Key"
                          />
                        </FormField>
                        <FormField
                          label="API Key"
                          htmlFor="auth_token"
                          required
                          error={formErrors.auth_token}
                          helpText="The API key value (can use environment variables like ${API_KEY})"
                        >
                          <Input
                            id="auth_token"
                            name="auth_token"
                            value={currentTool.auth_token || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., ${MCP_API_KEY}"
                          />
                        </FormField>
                      </>
                    )}

                    {currentTool.auth_type === "bearer" && (
                      <FormField
                        label="Bearer Token"
                        htmlFor="auth_token"
                        required
                        error={formErrors.auth_token}
                        helpText="The bearer token value (can use environment variables like ${TOKEN})"
                      >
                        <Input
                          id="auth_token"
                          name="auth_token"
                          value={currentTool.auth_token || ""}
                          onChange={handleModalChange}
                          placeholder="e.g., ${MCP_BEARER_TOKEN}"
                        />
                      </FormField>
                    )}

                    {currentTool.auth_type === "oauth2" && (
                      <>
                        <FormField
                          label="Client ID"
                          htmlFor="oauth2_client_id"
                          required
                          error={formErrors.oauth2_client_id}
                          helpText="OAuth2 client identifier"
                        >
                          <Input
                            id="oauth2_client_id"
                            name="oauth2_client_id"
                            value={currentTool.oauth2_client_id || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., ${OAUTH2_CLIENT_ID}"
                          />
                        </FormField>
                        <FormField
                          label="Client Secret"
                          htmlFor="oauth2_client_secret"
                          required
                          error={formErrors.oauth2_client_secret}
                          helpText="OAuth2 client secret"
                        >
                          <Input
                            id="oauth2_client_secret"
                            name="oauth2_client_secret"
                            value={currentTool.oauth2_client_secret || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., ${OAUTH2_CLIENT_SECRET}"
                            type="password"
                          />
                        </FormField>
                        <FormField
                          label="Authorization URL"
                          htmlFor="oauth2_authorization_url"
                          helpText="OAuth2 authorization endpoint URL"
                        >
                          <Input
                            id="oauth2_authorization_url"
                            name="oauth2_authorization_url"
                            value={currentTool.oauth2_authorization_url || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., https://provider.com/oauth/authorize"
                          />
                        </FormField>
                        <FormField
                          label="Token URL"
                          htmlFor="oauth2_token_url"
                          helpText="OAuth2 token endpoint URL"
                        >
                          <Input
                            id="oauth2_token_url"
                            name="oauth2_token_url"
                            value={currentTool.oauth2_token_url || ""}
                            onChange={handleModalChange}
                            placeholder="e.g., https://provider.com/oauth/token"
                          />
                        </FormField>
                        <ChipInput
                          id="oauth2_scopes"
                          label="OAuth2 Scopes (Optional)"
                          values={currentTool.oauth2_scopes || []}
                          onChange={(newValues) => handleChipInputChange("oauth2_scopes", newValues)}
                          helpText="OAuth2 permission scopes"
                          placeholder="No scopes added yet"
                          inputPlaceholder="e.g., email, profile, openid"
                        />
                      </>
                    )}

                    <FormField
                      label="Connection Timeout (seconds)"
                      htmlFor="mcp_timeout"
                      helpText="Timeout for MCP server connections (default: 30 seconds)"
                    >
                      <Input
                        id="mcp_timeout"
                        name="mcp_timeout"
                        type="number"
                        value={currentTool.mcp_timeout?.toString() || "30"}
                        onChange={handleModalChange}
                        placeholder="30"
                      />
                    </FormField>
                  </>
                )}
              </>
            )}

            {(modalView === "builtin-tool" || modalView === "custom") && (
              <>
                <ChipInput
                  id="required_scopes"
                  label="Required Scopes (Optional)"
                  values={currentTool.required_scopes || []}
                  onChange={(newValues) =>
                    handleChipInputChange("required_scopes", newValues)
                  }
                  helpText="Enter required OAuth scopes and press Add."
                  placeholder="No scopes added yet."
                  inputPlaceholder="e.g., read:profile"
                />
                <KeyValueInput
                  id="tool_config_ui"
                  label="Tool Config (Optional)"
                  values={currentTool.tool_config_ui || {}}
                  onChange={(values) => handleKeyValueInputChange("tool_config_ui", values)}
                  error={formErrors.tool_config_ui}
                  helpText="Tool-specific configuration like API keys, model names etc."
                  placeholder="No configuration added"
                  keyPlaceholder="Config key (e.g., api_key)"
                  valuePlaceholder="Config value"
                />
              </>
            )}

            {modalView !== "initial" && (
              <div className="flex justify-end space-x-2 mt-6 pt-4 border-t">
                <Button onClick={() => setIsModalOpen(false)} variant="outline">
                  Cancel
                </Button>
                <Button onClick={handleSaveTool}>
                  {editingToolId ? "Update Tool" : "Add Tool"}
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

      <div className="flex justify-end space-x-3 mt-8">
        <Button type="button" onClick={onPrevious} variant="outline">
          Previous
        </Button>
        <Button type="button" onClick={onNext}>
          Next
        </Button>
      </div>
    </div>
  );
};

export default AgentToolsStep;
