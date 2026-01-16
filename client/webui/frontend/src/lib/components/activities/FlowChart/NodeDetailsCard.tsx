import React, { useState, useEffect } from "react";
import { ArrowRight, Bot, CheckCircle, Eye, FileText, GitBranch, Loader2, RefreshCw, Terminal, User, Workflow, Wrench, X, Zap } from "lucide-react";
import type { NodeDetails } from "./utils/nodeDetailsHelper";
import { JSONViewer, MarkdownHTMLConverter } from "@/lib/components";
import type { VisualizerStep, ToolDecision } from "@/lib/types";
import { useChatContext } from "@/lib/hooks";
import { parseArtifactUri } from "@/lib/utils/download";
import { api } from "@/lib/api";

const MAX_ARTIFACT_DISPLAY_LENGTH = 5000;

interface ArtifactContentViewerProps {
    uri?: string;
    name: string;
    version?: number;
    mimeType?: string;
}

/**
 * Component to fetch and display artifact content inline
 */
const ArtifactContentViewer: React.FC<ArtifactContentViewerProps> = ({ uri, name, version, mimeType }) => {
    const { sessionId } = useChatContext();
    const [content, setContent] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isTruncated, setIsTruncated] = useState(false);

    useEffect(() => {
        const fetchContent = async () => {
            if (!uri && !name) return;

            setIsLoading(true);
            setError(null);

            try {
                let filename = name;
                let artifactVersion = version?.toString() || "latest";

                // Try to parse URI if available
                if (uri) {
                    const parsed = parseArtifactUri(uri);
                    if (parsed) {
                        filename = parsed.filename;
                        if (parsed.version) {
                            artifactVersion = parsed.version;
                        }
                    }
                }

                // Construct API endpoint
                const endpoint = `/api/v1/artifacts/${encodeURIComponent(sessionId || "null")}/${encodeURIComponent(filename)}/versions/${artifactVersion}`;

                const response = await api.webui.get(endpoint, { fullResponse: true, credentials: "include" });
                if (!response.ok) {
                    throw new Error(`Failed to fetch artifact: ${response.statusText}`);
                }

                const blob = await response.blob();
                const text = await blob.text();

                // Truncate if too long
                if (text.length > MAX_ARTIFACT_DISPLAY_LENGTH) {
                    setContent(text.substring(0, MAX_ARTIFACT_DISPLAY_LENGTH));
                    setIsTruncated(true);
                } else {
                    setContent(text);
                    setIsTruncated(false);
                }
            } catch (err) {
                console.error("Error fetching artifact:", err);
                setError(err instanceof Error ? err.message : "Failed to load artifact");
            } finally {
                setIsLoading(false);
            }
        };

        fetchContent();
    }, [uri, name, version, sessionId]);

    const renderContent = () => {
        if (!content) return null;

        const effectiveMimeType = mimeType || (name.endsWith(".json") ? "application/json" :
                                               name.endsWith(".yaml") || name.endsWith(".yml") ? "text/yaml" :
                                               name.endsWith(".csv") ? "text/csv" : "text/plain");

        // Try to parse and format JSON
        if (effectiveMimeType === "application/json" || name.endsWith(".json")) {
            try {
                const parsed = JSON.parse(content);
                return (
                    <div className="max-h-64 overflow-y-auto">
                        <JSONViewer data={parsed} />
                    </div>
                );
            } catch {
                // Fall through to plain text
            }
        }

        // For YAML, CSV, and other text formats, show as preformatted text
        return (
            <pre className="text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-w100) p-2 rounded overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
                {content}
            </pre>
        );
    };

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 text-xs text-(--color-secondary-text-wMain)">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading artifact content...
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-xs text-(--color-error-wMain) dark:text-(--color-error-w30)">
                {error}
            </div>
        );
    }

    if (!content) {
        return (
            <div className="text-xs text-(--color-secondary-text-wMain) italic">
                No content available
            </div>
        );
    }

    return (
        <div>
            {renderContent()}
            {isTruncated && (
                <div className="text-xs text-(--color-warning-wMain) dark:text-(--color-warning-w30) mt-1 italic">
                    Content truncated (showing first {MAX_ARTIFACT_DISPLAY_LENGTH.toLocaleString()} characters)
                </div>
            )}
        </div>
    );
};

interface NodeDetailsCardProps {
    nodeDetails: NodeDetails;
    onClose?: () => void;
    onWidthChange?: (isExpanded: boolean) => void;
}

/**
 * Component to display detailed request and result information for a clicked node
 */
const NodeDetailsCard: React.FC<NodeDetailsCardProps> = ({ nodeDetails, onClose, onWidthChange }) => {
    const { artifacts, setPreviewArtifact: setSidePanelPreviewArtifact, setActiveSidePanelTab, setIsSidePanelCollapsed, navigateArtifactVersion } = useChatContext();

    // Local state for inline artifact preview (NP-3)
    const [inlinePreviewArtifact, setInlinePreviewArtifact] = useState<{ name: string; version?: number; mimeType?: string } | null>(null);

    // Notify parent when expansion state changes
    useEffect(() => {
        onWidthChange?.(inlinePreviewArtifact !== null);
    }, [inlinePreviewArtifact, onWidthChange]);

    const getNodeIcon = () => {
        switch (nodeDetails.nodeType) {
            case 'user':
                return <User className="text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" size={20} />;
            case 'agent':
                return <Bot className="text-(--color-info-wMain) dark:text-(--color-info-w30)" size={20} />;
            case 'llm':
                return <Zap className="text-(--color-accent-n2-wMain) dark:text-(--color-accent-n2-w30)" size={20} />;
            case 'tool':
                return <Wrench className="text-(--color-accent-n7-w100) dark:text-(--color-accent-n7-wMain)" size={20} />;
            case 'switch':
                return <GitBranch className="text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" size={20} />;
            case 'loop':
                return <RefreshCw className="text-(--color-accent-n2-wMain) dark:text-(--color-accent-n2-w30)" size={20} />;
            case 'group':
                return <Workflow className="text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)" size={20} />;
            default:
                return <Terminal className="text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)" size={20} />;
        }
    };

    const renderStepContent = (step: VisualizerStep | undefined, isRequest: boolean) => {
        if (!step) {
            return (
                <div className="flex items-center justify-center h-full text-(--color-secondary-text-w50) dark:text-(--color-secondary-text-wMain) italic">
                    {isRequest ? "No request data available" : "No result data available"}
                </div>
            );
        }

        // Format timestamp with milliseconds
        const date = new Date(step.timestamp);
        const timeString = date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false, // Use 24-hour format
        });
        const milliseconds = String(date.getMilliseconds()).padStart(3, "0");
        const formattedTimestamp = `${timeString}.${milliseconds}`;

        return (
            <div className="space-y-3">
                {/* Timestamp */}
                <div className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) font-mono">
                    {formattedTimestamp}
                </div>

                {/* Step-specific content */}
                {renderStepTypeContent(step)}
            </div>
        );
    };

    const renderStepTypeContent = (step: VisualizerStep) => {
        switch (step.type) {
            case 'USER_REQUEST':
                return renderUserRequest(step);
            case 'WORKFLOW_AGENT_REQUEST':
                return renderWorkflowAgentRequest(step);
            case 'AGENT_RESPONSE_TEXT':
                return renderAgentResponse(step);
            case 'AGENT_LLM_CALL':
                return renderLLMCall(step);
            case 'AGENT_LLM_RESPONSE_TO_AGENT':
                return renderLLMResponse(step);
            case 'AGENT_LLM_RESPONSE_TOOL_DECISION':
                return renderLLMToolDecision(step);
            case 'AGENT_TOOL_INVOCATION_START':
                return renderToolInvocation(step);
            case 'AGENT_TOOL_EXECUTION_RESULT':
                return renderToolResult(step);
            case 'WORKFLOW_NODE_EXECUTION_START':
                // For agent nodes in workflows, show as agent invocation
                if (step.data.workflowNodeExecutionStart?.nodeType === 'agent') {
                    return renderWorkflowAgentInvocation(step);
                }
                return renderWorkflowNodeStart(step);
            case 'WORKFLOW_NODE_EXECUTION_RESULT':
                return renderWorkflowNodeResult(step);
            case 'WORKFLOW_EXECUTION_START':
                return renderWorkflowStart(step);
            case 'WORKFLOW_EXECUTION_RESULT':
                return renderWorkflowResult(step);
            default:
                return (
                    <div className="text-sm text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">
                        {step.title}
                    </div>
                );
        }
    };

    const renderUserRequest = (step: VisualizerStep) => (
        <div>
            <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">User Input</h4>
            {step.data.text && (
                <div className="prose prose-sm dark:prose-invert max-w-none p-3 bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) rounded-md max-h-96 overflow-y-auto">
                    <MarkdownHTMLConverter>{step.data.text}</MarkdownHTMLConverter>
                </div>
            )}
        </div>
    );

    const renderWorkflowAgentRequest = (step: VisualizerStep) => {
        const data = step.data.workflowAgentRequest;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    Workflow Agent Request
                </h4>
                <div className="space-y-3">
                    {data.nodeId && (
                        <div className="text-xs">
                            <span className="font-semibold text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">Node Id:</span>{' '}
                            <span className="text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">{data.nodeId}</span>
                        </div>
                    )}

                    {/* Instruction from workflow node */}
                    {data.instruction && (
                        <div>
                            <div className="text-xs font-semibold mb-1 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">Instruction:</div>
                            <div className="prose prose-sm dark:prose-invert max-w-none p-3 bg-(--color-info-w10) dark:bg-(--color-info-w100)/30 rounded-md overflow-y-auto border border-(--color-info-w20) dark:border-(--color-info-w100)">
                                <MarkdownHTMLConverter>{data.instruction}</MarkdownHTMLConverter>
                            </div>
                        </div>
                    )}

                    {/* Input as artifact reference */}
                    {data.inputArtifactRef && (
                        <div>
                            <div className="text-xs font-semibold mb-1 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) flex items-baseline gap-1 min-w-0">
                                <span className="flex-shrink-0">Input:</span>
                                <span className="font-normal text-(--color-secondary-text-wMain) truncate min-w-0" title={data.inputArtifactRef.name}>{data.inputArtifactRef.name}</span>
                                {data.inputArtifactRef.version !== undefined && (
                                    <span className="ml-1 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30) flex-shrink-0">v{data.inputArtifactRef.version}</span>
                                )}
                            </div>
                            <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                <ArtifactContentViewer
                                    uri={data.inputArtifactRef.uri}
                                    name={data.inputArtifactRef.name}
                                    version={data.inputArtifactRef.version}
                                    mimeType={data.inputArtifactRef.mimeType}
                                />
                            </div>
                        </div>
                    )}

                    {/* Input as text (for simple text schemas) */}
                    {data.inputText && !data.inputArtifactRef && (
                        <div>
                            <div className="text-xs font-semibold mb-1 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">Input:</div>
                            <div className="prose prose-sm dark:prose-invert max-w-none p-3 bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) rounded-md overflow-y-auto">
                                <MarkdownHTMLConverter>{data.inputText}</MarkdownHTMLConverter>
                            </div>
                        </div>
                    )}

                    {/* Input Schema */}
                    {data.inputSchema && (
                        <div>
                            <div className="text-xs font-semibold mb-1 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">Input Schema:</div>
                            <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70) max-h-48 overflow-y-auto">
                                <JSONViewer data={data.inputSchema} />
                            </div>
                        </div>
                    )}

                    {/* Output Schema */}
                    {data.outputSchema && (
                        <div>
                            <div className="text-xs font-semibold mb-1 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">Output Schema:</div>
                            <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70) max-h-48 overflow-y-auto">
                                <JSONViewer data={data.outputSchema} />
                            </div>
                        </div>
                    )}

                    {/* No input data available */}
                    {!data.inputText && !data.inputArtifactRef && !data.instruction && (
                        <div className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic">
                            No input data available
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderAgentResponse = (step: VisualizerStep) => (
        <div>
            <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">Agent Response</h4>
            {step.data.text && (
                <div className="prose prose-sm dark:prose-invert max-w-none p-3 bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) rounded-md overflow-y-auto">
                    <MarkdownHTMLConverter>{step.data.text}</MarkdownHTMLConverter>
                </div>
            )}
        </div>
    );

    const renderLLMCall = (step: VisualizerStep) => {
        const data = step.data.llmCall;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">LLM Request</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Model:</span> {data.modelName}
                    </div>
                    <div>
                        <div className="text-xs font-semibold mb-1">Prompt:</div>
                        <pre className="text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md overflow-auto max-h-80 whitespace-pre-wrap break-words">
                            {data.promptPreview}
                        </pre>
                    </div>
                </div>
            </div>
        );
    };

    const renderLLMResponse = (step: VisualizerStep) => {
        const data = step.data.llmResponseToAgent;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">LLM Response</h4>
                <div className="space-y-2">
                    {data.modelName && (
                        <div className="text-xs">
                            <span className="font-semibold">Model:</span> {data.modelName}
                        </div>
                    )}
                    <div>
                        <pre className="text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md overflow-auto max-h-80 whitespace-pre-wrap break-words">
                            {data.response || data.responsePreview}
                        </pre>
                    </div>
                    {data.isFinalResponse !== undefined && (
                        <div className="text-xs">
                            <span className="font-semibold">Final Response:</span> {data.isFinalResponse ? "Yes" : "No"}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderLLMToolDecision = (step: VisualizerStep) => {
        const data = step.data.toolDecision;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    LLM Tool Decision{data.isParallel ? " (Parallel)" : ""}
                </h4>
                <div className="space-y-3">
                    {data.decisions && data.decisions.length > 0 && (
                        <div>
                            <div className="text-xs font-semibold mb-2">Tools to invoke:</div>
                            <div className="space-y-2">
                                {data.decisions.map((decision: ToolDecision, index: number) => (
                                    <div
                                        key={index}
                                        className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)"
                                    >
                                        <div className="text-xs font-semibold text-(--color-info-wMain) dark:text-(--color-info-w30) mb-1">
                                            {decision.toolName}
                                            {decision.isPeerDelegation && (
                                                <span className="ml-2 px-1.5 py-0.5 bg-(--color-accent-n3-w10) dark:bg-(--color-accent-n3-w100)/30 text-(--color-accent-n3-w100) dark:text-(--color-accent-n3-w30) rounded text-xs">
                                                    {decision.toolName.startsWith('workflow_') ? 'Workflow' : 'Peer Agent'}
                                                </span>
                                            )}
                                        </div>
                                        {decision.toolArguments && Object.keys(decision.toolArguments).length > 0 && (
                                            <div className="mt-1">
                                                {renderFormattedArguments(decision.toolArguments)}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderToolInvocation = (step: VisualizerStep) => {
        const data = step.data.toolInvocationStart;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    {data.isPeerInvocation ? "Peer Agent Call" : "Tool Invocation"}
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Tool:</span> {data.toolName}
                    </div>
                    <div>
                        <div className="text-xs font-semibold mb-2">Arguments:</div>
                        {renderFormattedArguments(data.toolArguments)}
                    </div>
                </div>
            </div>
        );
    };

    const renderFormattedArguments = (args: Record<string, any>) => {
        const entries = Object.entries(args);

        if (entries.length === 0) {
            return (
                <div className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic">
                    No arguments
                </div>
            );
        }

        return (
            <div className="space-y-3">
                {entries.map(([key, value]) => (
                    <div key={key} className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70) overflow-hidden">
                        <div className="text-xs font-semibold text-(--color-info-wMain) dark:text-(--color-info-w30) mb-1">
                            {key}
                        </div>
                        <div className="text-xs overflow-auto max-h-60">
                            {renderArgumentValue(value)}
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    const renderArgumentValue = (value: any): React.ReactNode => {
        // Handle null/undefined
        if (value === null) {
            return <span className="text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic">null</span>;
        }
        if (value === undefined) {
            return <span className="text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic">undefined</span>;
        }

        // Handle primitives
        if (typeof value === 'string') {
            return <span className="text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10) whitespace-pre-wrap break-words">{value}</span>;
        }
        if (typeof value === 'number') {
            return <span className="text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)">{value}</span>;
        }
        if (typeof value === 'boolean') {
            return <span className="text-(--color-success-wMain) dark:text-(--color-success-w30)">{value.toString()}</span>;
        }

        // Handle arrays
        if (Array.isArray(value)) {
            if (value.length === 0) {
                return <span className="text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic">[]</span>;
            }
            // For simple arrays of primitives, show inline
            if (value.every(item => typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean')) {
                return (
                    <div className="space-y-1">
                        {value.map((item, idx) => (
                            <div key={idx} className="pl-2 border-l-2 border-(--color-info-w30) dark:border-(--color-info-w100)">
                                {renderArgumentValue(item)}
                            </div>
                        ))}
                    </div>
                );
            }
            // For complex arrays, use JSONViewer
            return (
                <div className="mt-1">
                    <JSONViewer data={value} />
                </div>
            );
        }

        // Handle objects
        if (typeof value === 'object') {
            const entries = Object.entries(value);

            // For small objects with simple values, render inline
            if (entries.length <= 5 && entries.every(([_, v]) =>
                typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' || v === null
            )) {
                return (
                    <div className="space-y-1">
                        {entries.map(([k, v]) => (
                            <div key={k} className="flex gap-2 min-w-0">
                                <span className="font-semibold text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) flex-shrink-0">{k}:</span>
                                <span className="min-w-0 break-words">{renderArgumentValue(v)}</span>
                            </div>
                        ))}
                    </div>
                );
            }

            // For complex objects, use JSONViewer
            return (
                <div className="mt-1">
                    <JSONViewer data={value} />
                </div>
            );
        }

        // Fallback
        return <span className="text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">{String(value)}</span>;
    };

    const renderToolResult = (step: VisualizerStep) => {
        const data = step.data.toolResult;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    {data.isPeerResponse ? "Peer Agent Result" : "Tool Result"}
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Tool:</span> {data.toolName}
                    </div>
                    <div>
                        <div className="text-xs font-semibold mb-2">Result:</div>
                        {typeof data.resultData === "object" && data.resultData !== null ? (
                            renderFormattedArguments(data.resultData)
                        ) : (
                            <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70) overflow-hidden">
                                <div className="text-xs overflow-auto max-h-60">
                                    {renderArgumentValue(data.resultData)}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    const renderWorkflowAgentInvocation = (step: VisualizerStep) => {
        const data = step.data.workflowNodeExecutionStart;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    Workflow Agent Invocation
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Agent:</span> {data.agentName || data.nodeId}
                    </div>
                    <div className="text-xs">
                        <span className="font-semibold">Workflow Node:</span> {data.nodeId}
                    </div>
                    {(data.iterationIndex !== undefined && data.iterationIndex !== null && typeof data.iterationIndex === 'number') && (
                        <div className="inline-block px-2 py-1 bg-(--color-info-w10) dark:bg-(--color-info-w100)/30 text-(--color-info-w100) dark:text-(--color-info-w10) rounded text-xs">
                            Iteration #{data.iterationIndex}
                        </div>
                    )}
                    {data.inputArtifactRef && (
                        <div className="mt-2">
                            <div className="text-xs font-semibold mb-1">Input:</div>
                            <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                <div className="text-xs">
                                    <div className="font-semibold text-(--color-info-wMain) dark:text-(--color-info-w30) mb-1">
                                        Artifact Reference
                                    </div>
                                    <div className="space-y-1">
                                        <div className="flex gap-2 min-w-0">
                                            <span className="font-semibold text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) flex-shrink-0">name:</span>
                                            <span className="text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10) truncate" title={data.inputArtifactRef.name}>{data.inputArtifactRef.name}</span>
                                        </div>
                                        {data.inputArtifactRef.version !== undefined && (
                                            <div className="flex gap-2">
                                                <span className="font-semibold text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) flex-shrink-0">version:</span>
                                                <span className="text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)">{data.inputArtifactRef.version}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    <div className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) italic mt-2">
                        This agent was invoked by the workflow with the input specified above.
                    </div>
                </div>
            </div>
        );
    };

    const renderWorkflowNodeStart = (step: VisualizerStep) => {
        const data = step.data.workflowNodeExecutionStart;
        if (!data) return null;

        // Switch node specific rendering
        if (data.nodeType === 'switch') {
            return (
                <div>
                    <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                        Switch Node
                    </h4>
                    <div className="space-y-3">
                        <div className="text-xs">
                            <span className="font-semibold">Node ID:</span> {data.nodeId}
                        </div>

                        {/* Cases */}
                        {data.cases && data.cases.length > 0 && (
                            <div>
                                <div className="text-xs font-semibold mb-2">Cases:</div>
                                <div className="space-y-2">
                                    {data.cases.map((caseItem, index) => (
                                        <div
                                            key={index}
                                            className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)"
                                        >
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-xs font-semibold text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)">
                                                    Case {index + 1}
                                                </span>
                                                <ArrowRight className="h-3 w-3 text-(--color-secondary-text-w50)" />
                                                <span className="text-xs font-medium text-(--color-info-wMain) dark:text-(--color-info-w30)">
                                                    {caseItem.node}
                                                </span>
                                            </div>
                                            <code className="block text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) break-all">
                                                {caseItem.condition}
                                            </code>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Default branch */}
                        {data.defaultBranch && (
                            <div className="bg-(--color-warning-w10) dark:bg-(--color-warning-w100)/30 p-2 rounded-md border border-(--color-warning-w20) dark:border-(--color-warning-w100)">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-(--color-warning-wMain) dark:text-(--color-warning-w30)">
                                        Default
                                    </span>
                                    <ArrowRight className="h-3 w-3 text-(--color-secondary-text-w50)" />
                                    <span className="text-xs font-medium text-(--color-info-wMain) dark:text-(--color-info-w30)">
                                        {data.defaultBranch}
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            );
        }

        // Loop node specific rendering
        if (data.nodeType === 'loop') {
            return (
                <div>
                    <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                        Loop Node
                    </h4>
                    <div className="space-y-2">
                        <div className="text-xs">
                            <span className="font-semibold">Node ID:</span> {data.nodeId}
                        </div>
                        {data.condition && (
                            <div>
                                <div className="text-xs font-semibold mb-1">Condition:</div>
                                <code className="block text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md break-all">
                                    {data.condition}
                                </code>
                            </div>
                        )}
                        {data.maxIterations !== undefined && (
                            <div className="text-xs">
                                <span className="font-semibold">Max Iterations:</span> {data.maxIterations}
                            </div>
                        )}
                        {data.loopDelay && (
                            <div className="text-xs">
                                <span className="font-semibold">Delay:</span> {data.loopDelay}
                            </div>
                        )}
                    </div>
                </div>
            );
        }

        // Default rendering for other node types
        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    Workflow Node Start
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Node ID:</span> {data.nodeId}
                    </div>
                    <div className="text-xs">
                        <span className="font-semibold">Type:</span> {data.nodeType}
                    </div>
                    {data.agentName && (
                        <div className="text-xs">
                            <span className="font-semibold">Agent:</span> {data.agentName}
                        </div>
                    )}
                    {data.condition && (
                        <div>
                            <div className="text-xs font-semibold mb-1">Condition:</div>
                            <code className="block text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md break-all">
                                {data.condition}
                            </code>
                        </div>
                    )}
                    {(data.iterationIndex !== undefined && data.iterationIndex !== null && typeof data.iterationIndex === 'number') && (
                        <div className="inline-block px-2 py-1 bg-(--color-info-w10) dark:bg-(--color-info-w100)/30 text-(--color-info-w100) dark:text-(--color-info-w10) rounded text-xs">
                            Iteration #{data.iterationIndex}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderWorkflowNodeResult = (step: VisualizerStep) => {
        const data = step.data.workflowNodeExecutionResult;
        if (!data) return null;

        // Extract switch-specific data from metadata
        const selectedBranch = data.metadata?.selected_branch;
        const selectedCaseIndex = data.metadata?.selected_case_index;
        const isSwitch = selectedBranch !== undefined || selectedCaseIndex !== undefined;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    {isSwitch ? "Switch Result" : "Workflow Node Result"}
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Status:</span>{" "}
                        <span className={
                            data.status === "success" ? "text-(--color-success-wMain) dark:text-(--color-success-w30)" :
                            data.status === "failure" ? "text-(--color-error-wMain) dark:text-(--color-error-w30)" :
                            "text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)"
                        }>
                            {data.status}
                        </span>
                    </div>

                    {/* Switch node result - selected branch */}
                    {selectedBranch !== undefined && (
                        <div className="mt-2 p-2 bg-(--color-success-w10) dark:bg-(--color-success-w100)/30 rounded-md border border-(--color-success-w20) dark:border-(--color-success-w100)">
                            <div className="flex items-center gap-2">
                                <CheckCircle className="h-4 w-4 text-(--color-success-wMain) dark:text-(--color-success-w30)" />
                                <span className="text-xs font-semibold text-(--color-success-w100) dark:text-(--color-success-w30)">
                                    Selected Branch:
                                </span>
                                <span className="text-xs font-bold text-(--color-success-w100) dark:text-(--color-success-w10)">
                                    {selectedBranch}
                                </span>
                            </div>
                            {selectedCaseIndex !== undefined && selectedCaseIndex !== null && (
                                <div className="mt-1 text-xs text-(--color-success-wMain) dark:text-(--color-success-w30)">
                                    Matched Case #{selectedCaseIndex + 1}
                                </div>
                            )}
                            {selectedCaseIndex === null && (
                                <div className="mt-1 text-xs text-(--color-warning-wMain) dark:text-(--color-warning-w30)">
                                    (Default branch - no case matched)
                                </div>
                            )}
                        </div>
                    )}

                    {data.conditionResult !== undefined && (
                        <div className="text-xs">
                            <span className="font-semibold">Condition Result:</span>{" "}
                            <span className={data.conditionResult ? "text-(--color-success-wMain) dark:text-(--color-success-w30) font-bold" : "text-(--color-warning-wMain) dark:text-(--color-warning-w30) font-bold"}>
                                {data.conditionResult ? "True" : "False"}
                            </span>
                        </div>
                    )}
                    {data.metadata?.condition && (
                        <div>
                            <div className="text-xs font-semibold mb-1">Condition:</div>
                            <code className="block text-xs bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md break-all">
                                {data.metadata.condition}
                            </code>
                        </div>
                    )}
                    {data.errorMessage && (
                        <div className="text-xs text-(--color-error-wMain) dark:text-(--color-error-w30)">
                            <span className="font-semibold">Error:</span> {data.errorMessage}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderWorkflowStart = (step: VisualizerStep) => {
        const data = step.data.workflowExecutionStart;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    Workflow Start
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Workflow:</span> {data.workflowName}
                    </div>
                    {data.workflowInput && (
                        <div>
                            <div className="text-xs font-semibold mb-2">Input:</div>
                            {renderFormattedArguments(data.workflowInput)}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const renderWorkflowResult = (step: VisualizerStep) => {
        const data = step.data.workflowExecutionResult;
        if (!data) return null;

        return (
            <div>
                <h4 className="text-sm font-semibold mb-2 text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10)">
                    Workflow Result
                </h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Status:</span>{" "}
                        <span className={data.status === "success" ? "text-(--color-success-wMain) dark:text-(--color-success-w30)" : "text-(--color-error-wMain) dark:text-(--color-error-w30)"}>
                            {data.status}
                        </span>
                    </div>
                    {data.workflowOutput && (
                        <div>
                            <div className="text-xs font-semibold mb-2">Output:</div>
                            {renderFormattedArguments(data.workflowOutput)}
                        </div>
                    )}
                    {data.errorMessage && (
                        <div className="text-xs text-(--color-error-wMain) dark:text-(--color-error-w30)">
                            <span className="font-semibold">Error:</span> {data.errorMessage}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    const hasRequestAndResult = nodeDetails.requestStep && nodeDetails.resultStep;
    const hasCreatedArtifacts = nodeDetails.createdArtifacts && nodeDetails.createdArtifacts.length > 0;

    // Helper to render output artifact if available
    const renderOutputArtifact = () => {
        const outputArtifactRef = nodeDetails.outputArtifactStep?.data?.workflowNodeExecutionResult?.outputArtifactRef;
        if (!outputArtifactRef) return null;

        return (
            <div className="mt-4 pt-4 border-t border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                <div className="text-xs font-semibold mb-2 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) flex items-baseline gap-1 min-w-0">
                    <span className="flex-shrink-0">Output Artifact:</span>
                    <span className="font-normal text-(--color-secondary-text-wMain) truncate min-w-0" title={outputArtifactRef.name}>{outputArtifactRef.name}</span>
                    {outputArtifactRef.version !== undefined && (
                        <span className="ml-1 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30) flex-shrink-0">v{outputArtifactRef.version}</span>
                    )}
                </div>
                <div className="bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) p-2 rounded-md border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                    <ArtifactContentViewer
                        name={outputArtifactRef.name}
                        version={outputArtifactRef.version}
                    />
                </div>
            </div>
        );
    };

    // Helper to render created artifacts for tool nodes
    // When asColumn is true, renders without the top border (for 3-column layout)
    const renderCreatedArtifacts = (asColumn: boolean = false) => {
        if (!nodeDetails.createdArtifacts || nodeDetails.createdArtifacts.length === 0) return null;

        const handleArtifactClick = (filename: string, version?: number) => {
            // Find the artifact by filename
            const artifact = artifacts.find(a => a.filename === filename);

            if (artifact) {
                // Switch to Files tab
                setActiveSidePanelTab("files");

                // Expand side panel if collapsed
                setIsSidePanelCollapsed(false);

                // Set preview artifact to open the file
                setSidePanelPreviewArtifact(artifact);

                // If a specific version is indicated, navigate to it
                if (version !== undefined && version !== artifact.version) {
                    // Wait a bit for the file to load, then navigate to the specific version
                    setTimeout(() => {
                        navigateArtifactVersion(filename, version);
                    }, 100);
                }

                // Close the popover
                onClose?.();
            }
        };

        return (
            <div className={asColumn ? "" : "mt-4 pt-4 border-t border-(--color-secondary-w20) dark:border-(--color-secondary-w70)"}>
                <div className={`flex items-center gap-2 ${asColumn ? "mb-3 pb-2 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70)" : "mb-3"}`}>
                    <div className={`${asColumn ? "w-2 h-2 rounded-full bg-(--color-accent-n1-wMain)" : ""}`}></div>
                    <FileText className={`h-4 w-4 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w30) ${asColumn ? "hidden" : ""}`} />
                    <h4 className="text-sm font-bold text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w30)">
                        {asColumn ? "CREATED ARTIFACTS" : `Created Artifacts (${nodeDetails.createdArtifacts.length})`}
                    </h4>
                </div>
                <div className="space-y-3">
                    {nodeDetails.createdArtifacts.map((artifact, index) => (
                        <div
                            key={`${artifact.filename}-${artifact.version ?? index}`}
                            className="bg-(--color-accent-n1-w10) dark:bg-(--color-accent-n1-w100)/30 p-3 rounded-md border border-(--color-accent-n1-w20) dark:border-(--color-accent-n1-w100)"
                        >
                            <div className="flex items-center justify-between gap-2 mb-1">
                                <button
                                    onClick={() => handleArtifactClick(artifact.filename, artifact.version)}
                                    className="text-sm font-semibold text-(--color-accent-n1-w100) dark:text-(--color-accent-n1-w30) hover:text-(--color-accent-n1-w100) dark:hover:text-(--color-accent-n1-w10) hover:underline cursor-pointer transition-colors truncate min-w-0"
                                    title={artifact.filename}
                                >
                                    {artifact.filename}
                                </button>
                                <div className="flex items-center gap-2 flex-shrink-0">
                                    {/* Inline preview button (NP-3) */}
                                    <button
                                        onClick={() => setInlinePreviewArtifact({
                                            name: artifact.filename,
                                            version: artifact.version,
                                            mimeType: artifact.mimeType
                                        })}
                                        className="p-1 rounded hover:bg-(--color-accent-n1-w20) dark:hover:bg-(--color-accent-n1-w100)/50 transition-colors"
                                        title="Preview inline"
                                    >
                                        <Eye className="h-3.5 w-3.5 text-(--color-accent-n1-wMain) dark:text-(--color-accent-n1-w30)" />
                                    </button>
                                    {artifact.version !== undefined && (
                                        <span className="text-xs px-1.5 py-0.5 bg-(--color-accent-n1-w20) dark:bg-(--color-accent-n1-w100)/50 text-(--color-accent-n1-w100) dark:text-(--color-accent-n1-w30) rounded">
                                            v{artifact.version}
                                        </span>
                                    )}
                                </div>
                            </div>
                            {artifact.description && (
                                <p className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) mb-2">
                                    {artifact.description}
                                </p>
                            )}
                            {artifact.mimeType && (
                                <div className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)">
                                    <span className="font-medium">Type:</span> {artifact.mimeType}
                                </div>
                            )}
                            <div className="mt-2 bg-(--color-background-w10) dark:bg-(--color-background-wMain) rounded border border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                <ArtifactContentViewer
                                    name={artifact.filename}
                                    version={artifact.version}
                                    mimeType={artifact.mimeType}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    // Render the main node details content
    const renderMainContent = () => (
        <div className="flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 p-4 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70) bg-(--color-secondary-w10) dark:bg-(--color-background-wMain) flex-shrink-0">
                {getNodeIcon()}
                <div className="min-w-0 flex-1">
                    <h3 className="text-base font-bold text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10) truncate">
                        {nodeDetails.label}
                    </h3>
                    {nodeDetails.description ? (
                        <p className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) truncate" title={nodeDetails.description}>
                            {nodeDetails.description}
                        </p>
                    ) : (
                        <p className="text-xs text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50) capitalize">
                            {nodeDetails.nodeType} Node
                        </p>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
                {hasRequestAndResult ? (
                    /* Split view for request and result (and optionally created artifacts) */
                    <div className={`grid grid-cols-1 ${hasCreatedArtifacts ? 'lg:grid-cols-3' : 'lg:grid-cols-2'} divide-y lg:divide-y-0 lg:divide-x divide-gray-200 dark:divide-gray-700`}>
                        {/* Request Column */}
                        <div className="p-4">
                            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                <div className="w-2 h-2 rounded-full bg-(--color-info-wMain)"></div>
                                <h4 className="text-sm font-bold text-(--color-info-wMain) dark:text-(--color-info-w30)">
                                    REQUEST
                                </h4>
                            </div>
                            {renderStepContent(nodeDetails.requestStep, true)}
                        </div>

                        {/* Result Column */}
                        <div className="p-4">
                            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                <div className="w-2 h-2 rounded-full bg-(--color-success-wMain)"></div>
                                <h4 className="text-sm font-bold text-(--color-success-wMain) dark:text-(--color-success-w30)">
                                    RESULT
                                </h4>
                            </div>
                            {renderStepContent(nodeDetails.resultStep, false)}
                            {renderOutputArtifact()}
                        </div>

                        {/* Created Artifacts Column (when present) */}
                        {hasCreatedArtifacts && (
                            <div className="p-4">
                                {renderCreatedArtifacts(true)}
                            </div>
                        )}
                    </div>
                ) : (
                    /* Single view when only request or result is available */
                    <div className="p-4">
                        {nodeDetails.requestStep && (
                            <div className="mb-4">
                                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                    <div className="w-2 h-2 rounded-full bg-(--color-info-wMain)"></div>
                                    <h4 className="text-sm font-bold text-(--color-info-wMain) dark:text-(--color-info-w30)">
                                        REQUEST
                                    </h4>
                                </div>
                                {renderStepContent(nodeDetails.requestStep, true)}
                            </div>
                        )}
                        {nodeDetails.resultStep && (
                            <div>
                                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70)">
                                    <div className="w-2 h-2 rounded-full bg-(--color-success-wMain)"></div>
                                    <h4 className="text-sm font-bold text-(--color-success-wMain) dark:text-(--color-success-w30)">
                                        RESULT
                                    </h4>
                                </div>
                                {renderStepContent(nodeDetails.resultStep, false)}
                                {renderOutputArtifact()}
                                {renderCreatedArtifacts()}
                            </div>
                        )}
                        {!nodeDetails.requestStep && !nodeDetails.resultStep && (
                            <div className="flex items-center justify-center h-32 text-(--color-secondary-text-w50) dark:text-(--color-secondary-text-wMain) italic">
                                No detailed information available for this node
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );

    // Render the inline artifact preview panel (NP-3)
    const renderArtifactPreviewPanel = () => {
        if (!inlinePreviewArtifact) return null;

        return (
            <div className="flex flex-col h-full overflow-hidden border-l border-(--color-secondary-w20) dark:border-(--color-secondary-w70) w-[500px]">
                {/* Preview Header */}
                <div className="flex items-center justify-between gap-3 p-4 border-b border-(--color-secondary-w20) dark:border-(--color-secondary-w70) bg-(--color-accent-n3-w10) dark:bg-(--color-accent-n3-w100)/30 flex-shrink-0">
                    <div className="flex items-center gap-2 min-w-0">
                        <FileText className="h-5 w-5 text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30) flex-shrink-0" />
                        <div className="min-w-0">
                            <h3 className="text-sm font-bold text-(--color-primary-text-wMain) dark:text-(--color-primary-text-w10) truncate" title={inlinePreviewArtifact.name}>
                                {inlinePreviewArtifact.name}
                            </h3>
                            {inlinePreviewArtifact.version !== undefined && (
                                <p className="text-xs text-(--color-accent-n3-wMain) dark:text-(--color-accent-n3-w30)">
                                    Version {inlinePreviewArtifact.version}
                                </p>
                            )}
                        </div>
                    </div>
                    <button
                        onClick={() => setInlinePreviewArtifact(null)}
                        className="p-1.5 rounded-md hover:bg-(--color-accent-n3-w10) dark:hover:bg-(--color-accent-n3-w100)/50 transition-colors flex-shrink-0"
                        title="Close preview"
                    >
                        <X className="h-4 w-4 text-(--color-secondary-text-wMain) dark:text-(--color-secondary-text-w50)" />
                    </button>
                </div>

                {/* Preview Content */}
                <div className="flex-1 overflow-y-auto p-4">
                    <ArtifactContentViewer
                        name={inlinePreviewArtifact.name}
                        version={inlinePreviewArtifact.version}
                        mimeType={inlinePreviewArtifact.mimeType}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-row h-full">
            {/* Main content */}
            <div className="flex-1 min-w-0">
                {renderMainContent()}
            </div>

            {/* Artifact preview panel (NP-3) */}
            {renderArtifactPreviewPanel()}
        </div>
    );
};

export default NodeDetailsCard;
