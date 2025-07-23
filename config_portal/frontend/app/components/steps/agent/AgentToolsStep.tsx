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

export interface Tool {
  id?: string;
  tool_type: "python" | "mcp" | "builtin" | "builtin-group" | "";
  tool_name?: string;
  tool_description?: string;
  group_name?: string;
  component_module?: string;
  function_name?: string;
  component_base_path?: string;
  connection_params_str?: string;
  environment_variables_str?: string;
  tool_config_str?: string;

  connection_params?: Record<string, unknown>;
  environment_variables?: Record<string, unknown>;
  required_scopes?: string[];
  tool_config?: Record<string, unknown>;
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
  connection_params_str: "{}",
  environment_variables_str: "{}",
  tool_config_str: "{}",
  connection_params: undefined,
  environment_variables: undefined,
  required_scopes: [],
  tool_config: undefined,
};

const parseJsonString = (
  jsonStr: string | undefined,
  defaultValue: Record<string, unknown> | undefined = undefined
): Record<string, unknown> | undefined => {
  if (jsonStr === undefined || jsonStr.trim() === "" || jsonStr.trim() === "{}")
    return defaultValue;
  try {
    const parsed = JSON.parse(jsonStr);
    return typeof parsed === "object" &&
      parsed !== null &&
      !Array.isArray(parsed)
      ? parsed
      : defaultValue;
  } catch (e) {
    console.warn("Failed to parse JSON string:", jsonStr, e);
    return defaultValue;
  }
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
    const toolForEdit: Tool = {
      ...initialToolState,
      ...tool,
      id: tool.id || Date.now().toString(),
      tool_type: tool.tool_type || "",
      connection_params_str: tool.connection_params
        ? JSON.stringify(tool.connection_params, null, 2)
        : "{}",
      environment_variables_str: tool.environment_variables
        ? JSON.stringify(tool.environment_variables, null, 2)
        : "{}",
      tool_config_str: tool.tool_config
        ? JSON.stringify(tool.tool_config, null, 2)
        : "{}",
      required_scopes: Array.isArray(tool.required_scopes)
        ? tool.required_scopes
        : [],
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
    setCurrentTool((prev) => ({ ...prev, [name]: value }));

    if (
      name === "connection_params_str" ||
      name === "environment_variables_str" ||
      name === "tool_config_str"
    ) {
      if (value.trim() === "" || value.trim() === "{}") {
        setFormErrors((prev) => ({ ...prev, [name]: undefined }));
      } else {
        try {
          const parsed = JSON.parse(value);
          if (
            typeof parsed !== "object" ||
            parsed === null ||
            Array.isArray(parsed)
          ) {
            setFormErrors((prev) => ({
              ...prev,
              [name]: "Must be a valid JSON object.",
            }));
          } else if (
            name === "connection_params_str" &&
            (!parsed.type || !parsed.command || !parsed.args)
          ) {
            setFormErrors((prev) => ({
              ...prev,
              [name]:
                "Connection parameters must include type, command, and args.",
            }));
          } else {
            setFormErrors((prev) => ({ ...prev, [name]: undefined }));
          }
        } catch (error) {
          setFormErrors((prev) => ({
            ...prev,
            [name]: "Invalid JSON format.",
          }));
        }
      }
    }
  };

  const handleChipInputChange = (fieldName: keyof Tool, values: string[]) => {
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
      if (
        !currentTool.connection_params_str ||
        currentTool.connection_params_str.trim() === "{}"
      ) {
        errors.connection_params_str =
          "Connection parameters are required for MCP tools.";
      }
    }
    if (currentTool.connection_params_str)
      try {
        parseJsonString(currentTool.connection_params_str, undefined);
      } catch (e) {
        errors.connection_params_str =
          "Invalid JSON format for Connection Parameters.";
      }
    if (currentTool.environment_variables_str)
      try {
        parseJsonString(currentTool.environment_variables_str, undefined);
      } catch (e) {
        errors.environment_variables_str =
          "Invalid JSON format for Environment Variables.";
      }
    if (currentTool.tool_config_str)
      try {
        parseJsonString(currentTool.tool_config_str, undefined);
      } catch (e) {
        errors.tool_config_str = "Invalid JSON format for Tool Config.";
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
          tool_config: parseJsonString(currentTool.tool_config_str, undefined),
          required_scopes: currentTool.required_scopes || [],
        };
        break;
      case "mcp":
        processedTool = {
          ...baseTool,
          tool_name: currentTool.tool_name || undefined,
          connection_params: parseJsonString(
            currentTool.connection_params_str,
            undefined
          ),
          environment_variables: parseJsonString(
            currentTool.environment_variables_str,
            undefined
          ),
          tool_config: parseJsonString(currentTool.tool_config_str, undefined),
          required_scopes: currentTool.required_scopes || [],
        };
        break;
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
    updateData({ tools: newToolsList });
    setIsModalOpen(false);
    setEditingToolId(null);
  };

  const handleDeleteTool = (toolId?: string) => {
    if (!toolId) return;
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
                      label="Connection Parameters (JSON)"
                      htmlFor="connection_params_str"
                      error={formErrors.connection_params_str}
                      helpText='E.g., {"type": "stdio", "command": "cmd", "args":[]}'
                    >
                      <textarea
                        id="connection_params_str"
                        name="connection_params_str"
                        rows={4}
                        value={currentTool.connection_params_str || "{}"}
                        onChange={handleModalChange}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm font-mono text-xs"
                      />
                    </FormField>
                    <FormField
                      label="Environment Variables (JSON, Optional)"
                      htmlFor="environment_variables_str"
                      error={formErrors.environment_variables_str}
                    >
                      <textarea
                        id="environment_variables_str"
                        name="environment_variables_str"
                        rows={3}
                        value={currentTool.environment_variables_str || "{}"}
                        onChange={handleModalChange}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm font-mono text-xs"
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
                <FormField
                  label="Tool Config (JSON, Optional)"
                  htmlFor="tool_config_str"
                  error={formErrors.tool_config_str}
                  helpText="Tool-specific configuration like API keys, model names etc."
                >
                  <textarea
                    id="tool_config_str"
                    name="tool_config_str"
                    rows={3}
                    value={currentTool.tool_config_str || "{}"}
                    onChange={handleModalChange}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm font-mono text-xs"
                  />
                </FormField>
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
