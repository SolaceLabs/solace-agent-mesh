import { useState, useEffect } from "react";
import { ArrowRight, Bot, CheckCircle, FileText, GitBranch, Loader2, RefreshCw, Terminal, User, Workflow, Wrench, Zap } from "lucide-react";

import { useChatContext } from "@/lib/hooks";
import { type JSONValue, JSONViewer, MarkdownHTMLConverter } from "@/lib/components";
import { getRenderType, getFileContent, decodeBase64Content, encodeBase64Content, ContentRenderer } from "@/lib/components/chat/preview";
import type { VisualizerStep, ToolDecision, FileAttachment } from "@/lib/types";
import { parseArtifactUri, getArtifactContent } from "@/lib/utils";

import type { NodeDetails } from "./utils/nodeDetailsHelper";

const MAX_ARTIFACT_DISPLAY_LENGTH = 1000;

const ColumnHeader = ({ label, color }: { label: string; color: string }) => {
    return (
        <div className="mb-3 flex items-center gap-2 border-b pb-2">
            <div className={`h-2 w-2 rounded-full bg-${color}`}></div>
            <h4 className={`text-sm font-bold text-${color}`}>{label}</h4>
        </div>
    );
};

interface ArtifactContentViewerProps {
    uri?: string;
    name: string;
    version?: number;
    mimeType?: string;
}

const isNotTruncatable = (renderType: string) => renderType === "image" || renderType === "audio" || renderType === "html";

/**
 * Component to fetch and display artifact content inline.
 * Supports binary artifacts (images, audio) as well as text-based artifacts.
 */
const ArtifactContentViewer = ({ uri, name, version, mimeType }: ArtifactContentViewerProps) => {
    const { sessionId } = useChatContext();
    const [content, setContent] = useState<string | null>(null);
    const [fetchedMimeType, setFetchedMimeType] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isTruncated, setIsTruncated] = useState(false);

    useEffect(() => {
        const fetchContent = async () => {
            if ((!sessionId && !uri) || !name) return;

            setIsLoading(true);
            setError(null);

            try {
                let parsedFileName;
                let parsedSessionId;
                let parsedVersion;

                // Parse uri to validate props
                if (uri) {
                    const parsed = parseArtifactUri(uri);
                    if (parsed) {
                        parsedFileName = parsed.filename;
                        parsedSessionId = parsed.sessionId;
                        if (parsed.version) {
                            const uriVersion = parseInt(parsed.version, 10);
                            parsedVersion = Number.isInteger(uriVersion) ? uriVersion : undefined;
                        }
                    }
                }

                const { content, mimeType: responseMimeType } = await getArtifactContent({
                    filename: parsedFileName ?? name,
                    sessionId: parsedSessionId ?? sessionId,
                    version: parsedVersion ?? version,
                });
                setFetchedMimeType(responseMimeType);

                // Only truncate text-based content - never truncate binary (image, audio)
                const currentRenderType = getRenderType(parsedFileName ?? name, responseMimeType);
                const shouldTruncate = currentRenderType && !isNotTruncatable(currentRenderType);

                if (shouldTruncate) {
                    const decodedText = decodeBase64Content(content);
                    if (decodedText.length > MAX_ARTIFACT_DISPLAY_LENGTH) {
                        const truncatedText = decodedText.substring(0, MAX_ARTIFACT_DISPLAY_LENGTH);
                        setContent(encodeBase64Content(truncatedText));
                        setIsTruncated(true);
                    } else {
                        setContent(content);
                        setIsTruncated(false);
                    }
                } else {
                    setContent(content);
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

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 text-xs">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading artifact content...
            </div>
        );
    }

    if (error) {
        return <div className="text-destructive text-xs">{error}</div>;
    }

    if (!content) {
        return <div className="text-secondary-foreground text-xs">No content available</div>;
    }

    // Derive render type from filename and fetched mime type
    const effectiveMimeType = fetchedMimeType || mimeType;
    const renderType = getRenderType(name, effectiveMimeType);

    // No supported render type - show message
    if (!renderType) {
        return <div className="text-secondary-foreground text-xs">Preview not available for this file type</div>;
    }

    // Create a FileAttachment-like object for getFileContent
    const fileAttachment: FileAttachment = {
        name,
        mime_type: effectiveMimeType,
        content,
    };
    const processedContent = getFileContent(fileAttachment);

    if (!processedContent) {
        return <div className="text-secondary-foreground text-xs">No content available</div>;
    }

    return (
        <>
            <div className={`overflow-y-auto ${renderType === "html" ? "h-[calc(50vh-100px)]" : "max-h-[calc(50vh-100px)]"}`}>
                <ContentRenderer content={processedContent} rendererType={renderType} mime_type={effectiveMimeType} setRenderError={setError} />
            </div>
            {isTruncated && <div className="mt-2 text-xs text-(--color-info-wMain)">Content truncated at first {MAX_ARTIFACT_DISPLAY_LENGTH.toLocaleString()} characters</div>}
        </>
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
const NodeDetailsCard = ({ nodeDetails, onClose }: NodeDetailsCardProps) => {
    const { artifacts, setPreviewArtifact: setSidePanelPreviewArtifact, setActiveSidePanelTab, setIsSidePanelCollapsed, navigateArtifactVersion } = useChatContext();

    const getNodeIcon = () => {
        switch (nodeDetails.nodeType) {
            case "user":
                return <User className="text-purple-500 dark:text-purple-400" size={20} />;
            case "agent":
                return <Bot className="text-(--color-brand-wMain)" size={20} />;
            case "llm":
                return <Zap className="text-teal-500 dark:text-teal-400" size={20} />;
            case "tool":
                return <Wrench className="text-cyan-500 dark:text-cyan-400" size={20} />;
            case "switch":
                return <GitBranch className="text-purple-500 dark:text-purple-400" size={20} />;
            case "loop":
                return <RefreshCw className="text-teal-500 dark:text-teal-400" size={20} />;
            case "group":
                return <Workflow className="text-purple-500 dark:text-purple-400" size={20} />;
            default:
                return <Terminal className="text-secondary-foreground" size={20} />;
        }
    };

    const renderStepContent = (step: VisualizerStep | undefined, isRequest: boolean) => {
        if (!step) {
            return <div className="text-secondary-foreground flex h-full items-center justify-center">{isRequest ? "No request data available" : "No result data available"}</div>;
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
                <div className="text-secondary-foreground font-mono text-xs">{formattedTimestamp}</div>

                {/* Step-specific content */}
                {renderStepTypeContent(step)}
            </div>
        );
    };

    const renderStepTypeContent = (step: VisualizerStep) => {
        switch (step.type) {
            case "USER_REQUEST":
                return renderUserRequest(step);
            case "WORKFLOW_AGENT_REQUEST":
                return renderWorkflowAgentRequest(step);
            case "AGENT_RESPONSE_TEXT":
                return renderAgentResponse(step);
            case "AGENT_LLM_CALL":
                return renderLLMCall(step);
            case "AGENT_LLM_RESPONSE_TO_AGENT":
                return renderLLMResponse(step);
            case "AGENT_LLM_RESPONSE_TOOL_DECISION":
                return renderLLMToolDecision(step);
            case "AGENT_TOOL_INVOCATION_START":
                return renderToolInvocation(step);
            case "AGENT_TOOL_EXECUTION_RESULT":
                return renderToolResult(step);
            case "WORKFLOW_NODE_EXECUTION_START":
                // For agent nodes in workflows, show as agent invocation
                if (step.data.workflowNodeExecutionStart?.nodeType === "agent") {
                    return renderWorkflowAgentInvocation(step);
                }
                return renderWorkflowNodeStart(step);
            case "WORKFLOW_NODE_EXECUTION_RESULT":
                return renderWorkflowNodeResult(step);
            case "WORKFLOW_EXECUTION_START":
                return renderWorkflowStart(step);
            case "WORKFLOW_EXECUTION_RESULT":
                return renderWorkflowResult(step);
            default:
                return <div className="text-sm">{step.title}</div>;
        }
    };

    const renderUserRequest = (step: VisualizerStep) => (
        <div>
            <h4 className="mb-2 text-sm font-semibold">User Input</h4>
            {step.data.text && (
                <div className="prose prose-sm dark:prose-invert bg-muted/50 max-h-96 max-w-none overflow-y-auto rounded-md p-3">
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
                <h4 className="mb-2 text-sm font-semibold">Workflow Agent Request</h4>
                <div className="space-y-3">
                    {data.nodeId && (
                        <div className="text-xs">
                            <span className="font-semibold">Node Id:</span> <span>{data.nodeId}</span>
                        </div>
                    )}

                    {/* Instruction from workflow node */}
                    {data.instruction && (
                        <div>
                            <div className="mb-1 text-xs font-semibold">Instruction:</div>
                            <div className="prose prose-sm dark:prose-invert max-w-none overflow-y-auto rounded-md border border-(--color-info-w100) bg-(--color-info-w10) p-3 dark:bg-(--color-info-w100)/50">
                                <MarkdownHTMLConverter>{data.instruction}</MarkdownHTMLConverter>
                            </div>
                        </div>
                    )}

                    {/* Input as artifact reference */}
                    {data.inputArtifactRef && (
                        <div>
                            <div className="mb-1 flex min-w-0 items-baseline gap-1 text-xs font-semibold">
                                <span className="flex-shrink-0">Input:</span>
                                <span className="text-muted-foreground min-w-0 truncate font-normal" title={data.inputArtifactRef.name}>
                                    {data.inputArtifactRef.name}
                                </span>
                                {data.inputArtifactRef.version !== undefined && <span className="ml-1 flex-shrink-0 text-purple-600 dark:text-purple-400">v{data.inputArtifactRef.version}</span>}
                            </div>

                            <ArtifactContentViewer uri={data.inputArtifactRef.uri} name={data.inputArtifactRef.name} version={data.inputArtifactRef.version} />
                        </div>
                    )}

                    {/* Input as text (for simple text schemas) */}
                    {data.inputText && !data.inputArtifactRef && (
                        <div>
                            <div className="mb-1 text-xs font-semibold">Input:</div>
                            <div className="prose prose-sm dark:prose-invert bg-muted/50 max-w-none overflow-y-auto rounded-md p-3">
                                <MarkdownHTMLConverter>{data.inputText}</MarkdownHTMLConverter>
                            </div>
                        </div>
                    )}

                    {/* Input Schema */}
                    {data.inputSchema && (
                        <div>
                            <div className="mb-1 text-xs font-semibold">Input Schema:</div>
                            <div className="my-1 max-h-48 overflow-y-auto py-2">
                                <JSONViewer data={data.inputSchema} maxDepth={0} />
                            </div>
                        </div>
                    )}

                    {/* Output Schema */}
                    {data.outputSchema && (
                        <div>
                            <div className="mb-1 text-xs font-semibold">Output Schema:</div>
                            <div className="my-1 max-h-48 overflow-y-auto py-2">
                                <JSONViewer data={data.outputSchema} maxDepth={0} />
                            </div>
                        </div>
                    )}

                    {/* No input data available */}
                    {!data.inputText && !data.inputArtifactRef && !data.instruction && <div className="text-secondary-foreground text-xs italic">No input data available</div>}
                </div>
            </div>
        );
    };

    const renderAgentResponse = (step: VisualizerStep) => (
        <div>
            <h4 className="mb-2 text-sm font-semibold">Agent Response</h4>
            {step.data.text && (
                <div className="prose prose-sm dark:prose-invert bg-muted/50 max-w-none overflow-y-auto rounded-md p-3">
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
                <h4 className="mb-2 text-sm font-semibold">LLM Request</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Model:</span> {data.modelName}
                    </div>
                    <div>
                        <div className="mb-1 text-xs font-semibold">Prompt:</div>
                        <pre className="bg-muted/50 max-h-80 overflow-auto rounded-md p-2 text-xs break-words whitespace-pre-wrap">{data.promptPreview}</pre>
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
                <h4 className="mb-2 text-sm font-semibold">LLM Response</h4>
                <div className="space-y-2">
                    {data.modelName && (
                        <div className="text-xs">
                            <span className="font-semibold">Model:</span> {data.modelName}
                        </div>
                    )}
                    <div>
                        <pre className="bg-muted/50 max-h-80 overflow-auto rounded-md p-2 text-xs break-words whitespace-pre-wrap">{data.response || data.responsePreview}</pre>
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
                <h4 className="mb-2 text-sm font-semibold">LLM Tool Decision{data.isParallel ? " (Parallel)" : ""}</h4>
                <div className="space-y-3">
                    {data.decisions && data.decisions.length > 0 && (
                        <div>
                            <div className="mb-2 text-xs font-semibold">Tools to invoke:</div>
                            <div className="space-y-2">
                                {data.decisions.map((decision: ToolDecision, index: number) => (
                                    <div key={index} className="rounded-md border p-2">
                                        <div className="mb-1 text-xs font-semibold text-(--color-info-wMain)">
                                            {decision.toolName}
                                            {decision.isPeerDelegation && (
                                                <span className="ml-2 rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700 dark:bg-purple-900 dark:text-purple-300">{decision.toolName.startsWith("workflow_") ? "Workflow" : "Peer Agent"}</span>
                                            )}
                                        </div>
                                        {decision.toolArguments && Object.keys(decision.toolArguments).length > 0 && <div className="mt-1">{renderFormattedArguments(decision.toolArguments)}</div>}
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
                <h4 className="mb-2 text-sm font-semibold">{data.isPeerInvocation ? "Peer Agent Call" : "Tool Invocation"}</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Tool:</span> {data.toolName}
                    </div>
                    <div>
                        <div className="mb-2 text-xs font-semibold">Arguments:</div>
                        {renderFormattedArguments(data.toolArguments)}
                    </div>
                </div>
            </div>
        );
    };

    const renderFormattedArguments = (args: Record<string, unknown>) => {
        const entries = Object.entries(args);

        if (entries.length === 0) {
            return <div className="text-muted-foreground text-xs italic">No arguments</div>;
        }

        return (
            <div className="space-y-3">
                {entries.map(([key, value]) => (
                    <div key={key} className="overflow-hidden rounded-md border p-2">
                        <div className="mb-1 text-xs font-semibold text-(--color-info-wMain)">{key}</div>
                        <div className="max-h-60 overflow-auto text-xs">{renderArgumentValue(value)}</div>
                    </div>
                ))}
            </div>
        );
    };

    const renderArgumentValue = (value: unknown): React.ReactNode => {
        // Handle null/undefined
        if (value === null) {
            return <span className="text-secondary-foreground italic">null</span>;
        }
        if (value === undefined) {
            return <span className="text-secondary-foreground italic">undefined</span>;
        }

        // Handle primitives
        if (typeof value === "string") {
            return <span className="break-words whitespace-pre-wrap">{value}</span>;
        }
        if (typeof value === "number") {
            return <span className="text-purple-600 dark:text-purple-400">{value}</span>;
        }
        if (typeof value === "boolean") {
            return <span className="text-(--color-success-wMain)">{value.toString()}</span>;
        }

        // Handle arrays
        if (Array.isArray(value)) {
            if (value.length === 0) {
                return <span className="text-secondary-foreground italic">[]</span>;
            }
            // For simple arrays of primitives, show inline
            if (value.every(item => typeof item === "string" || typeof item === "number" || typeof item === "boolean")) {
                return (
                    <div className="space-y-1">
                        {value.map((item, idx) => (
                            <div key={idx} className="border-l-2 border-(--color-info-wMain) pl-2">
                                {renderArgumentValue(item)}
                            </div>
                        ))}
                    </div>
                );
            }
            // For complex arrays, use JSONViewer
            return (
                <div className="my-1">
                    <JSONViewer data={value} maxDepth={0} />
                </div>
            );
        }

        // Handle objects
        if (typeof value === "object") {
            const entries = Object.entries(value);

            // For small objects with simple values, render inline
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            if (entries.length <= 5 && entries.every(([_, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null)) {
                return (
                    <div className="space-y-1">
                        {entries.map(([k, v]) => (
                            <div key={k} className="flex min-w-0 gap-2">
                                <span className="flex-shrink-0 font-semibold">{k}:</span>
                                <span className="min-w-0 break-words">{renderArgumentValue(v)}</span>
                            </div>
                        ))}
                    </div>
                );
            }

            // For complex objects, use JSONViewer
            return (
                <div className="my-1">
                    <JSONViewer data={value as JSONValue} maxDepth={0} />
                </div>
            );
        }

        // Fallback
        return <span className="text-secondary-foreground">{String(value)}</span>;
    };

    const renderToolResult = (step: VisualizerStep) => {
        const data = step.data.toolResult;
        if (!data) return null;

        return (
            <div>
                <h4 className="mb-2 text-sm font-semibold">{data.isPeerResponse ? "Peer Agent Result" : "Tool Result"}</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Tool:</span> {data.toolName}
                    </div>
                    <div>
                        <div className="mb-2 text-xs font-semibold">Result:</div>
                        {typeof data.resultData === "object" && data.resultData !== null ? (
                            renderFormattedArguments(data.resultData)
                        ) : (
                            <div className="bg-muted/50 overflow-hidden rounded-md border p-2">
                                <div className="max-h-60 overflow-auto text-xs">{renderArgumentValue(data.resultData)}</div>
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
                <h4 className="mb-2 text-sm font-semibold">Workflow Agent Invocation</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Agent:</span> {data.agentName || data.nodeId}
                    </div>
                    <div className="text-xs">
                        <span className="font-semibold">Workflow Node:</span> {data.nodeId}
                    </div>
                    {data.iterationIndex !== undefined && data.iterationIndex !== null && typeof data.iterationIndex === "number" && (
                        <div className="inline-block rounded bg-(--color-info-w10) px-2 py-1 text-xs text-(--color-info-wMain) dark:bg-(--color-info-w100)/50">Iteration #{data.iterationIndex}</div>
                    )}
                    {data.inputArtifactRef && (
                        <div className="mt-2">
                            <div className="mb-1 text-xs font-semibold">Input:</div>
                            <div className="bg-muted/50 rounded-md border p-2">
                                <div className="text-xs">
                                    <div className="mb-1 font-semibold text-(--color-info-wMain)">Artifact Reference</div>
                                    <div className="space-y-1">
                                        <div className="flex min-w-0 gap-2">
                                            <span className="flex-shrink-0 font-semibold">name:</span>
                                            <span className="truncate" title={data.inputArtifactRef.name}>
                                                {data.inputArtifactRef.name}
                                            </span>
                                        </div>
                                        {data.inputArtifactRef.version !== undefined && (
                                            <div className="flex gap-2">
                                                <span className="flex-shrink-0 font-semibold">version:</span>
                                                <span className="text-purple-600 dark:text-purple-400">{data.inputArtifactRef.version}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    <div className="text-muted-foreground mt-2 text-xs italic">This agent was invoked by the workflow with the input specified above.</div>
                </div>
            </div>
        );
    };

    const renderWorkflowNodeStart = (step: VisualizerStep) => {
        const data = step.data.workflowNodeExecutionStart;
        if (!data) return null;

        // Switch node specific rendering
        if (data.nodeType === "switch") {
            return (
                <div>
                    <h4 className="mb-2 text-sm font-semibold">Switch Node</h4>
                    <div className="space-y-3">
                        <div className="text-xs">
                            <span className="font-semibold">Node ID:</span> {data.nodeId}
                        </div>

                        {/* Cases */}
                        {data.cases && data.cases.length > 0 && (
                            <div>
                                <div className="mb-2 text-xs font-semibold">Cases:</div>
                                <div className="space-y-2">
                                    {data.cases.map((caseItem, index) => (
                                        <div key={index} className="bg-muted/50 rounded-md border p-2">
                                            <div className="mb-1 flex items-center gap-2">
                                                <span className="text-xs font-semibold text-purple-600 dark:text-purple-400">Case {index + 1}</span>
                                                <ArrowRight className="text-secondary-foreground h-3 w-3" />
                                                <span className="text-xs font-medium text-(--color-info-wMain)">{caseItem.node}</span>
                                            </div>
                                            <code className="text-muted-foreground block text-xs break-all">{caseItem.condition}</code>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Default branch */}
                        {data.defaultBranch && (
                            <div className="rounded-md border border-(--color-warning-w100) p-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold text-(--color-warning-wMain)">Default</span>
                                    <ArrowRight className="text-secondary-foreground h-3 w-3" />
                                    <span className="text-xs font-medium text-(--color-info-wMain)">{data.defaultBranch}</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            );
        }

        // Loop node specific rendering
        if (data.nodeType === "loop") {
            return (
                <div>
                    <h4 className="mb-2 text-sm font-semibold">Loop Node</h4>
                    <div className="space-y-2">
                        <div className="text-xs">
                            <span className="font-semibold">Node ID:</span> {data.nodeId}
                        </div>
                        {data.condition && (
                            <div>
                                <div className="mb-1 text-xs font-semibold">Condition:</div>
                                <code className="bg-muted/50 block rounded-md p-2 text-xs break-all">{data.condition}</code>
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
                <h4 className="mb-2 text-sm font-semibold">Workflow Node Start</h4>
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
                            <div className="mb-1 text-xs font-semibold">Condition:</div>
                            <code className="bg-muted/50 block rounded-md p-2 text-xs break-all">{data.condition}</code>
                        </div>
                    )}
                    {data.iterationIndex !== undefined && data.iterationIndex !== null && typeof data.iterationIndex === "number" && (
                        <div className="inline-block rounded bg-(--color-info-w10) px-2 py-1 text-xs text-(--color-info-wMain) dark:bg-(--color-info-w100)/50">Iteration #{data.iterationIndex}</div>
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
                <h4 className="mb-2 text-sm font-semibold">{isSwitch ? "Switch Result" : "Workflow Node Result"}</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Status:</span> <span className={data.status === "success" ? "text-(--color-success-wMain)" : data.status === "failure" ? "text-destructive" : ""}>{data.status}</span>
                    </div>

                    {/* Switch node result - selected branch */}
                    {selectedBranch !== undefined && (
                        <div className="mt-2 rounded-md border border-(--color-success-wMain) p-2">
                            <div className="flex items-center gap-2">
                                <CheckCircle className="h-4 w-4 text-(--color-success-wMain)" />
                                <span className="text-xs font-semibold text-(--color-success-wMain)">Selected Branch:</span>
                                <span className="text-xs font-bold text-(--color-success-wMain)">{selectedBranch}</span>
                            </div>
                            {selectedCaseIndex !== undefined && selectedCaseIndex !== null && <div className="mt-1 text-xs text-(--color-success-wMain)">Matched Case #{selectedCaseIndex + 1}</div>}
                            {selectedCaseIndex === null && <div className="mt-1 text-xs text-(--color-warning-wMain)">(Default branch - no case matched)</div>}
                        </div>
                    )}

                    {data.conditionResult !== undefined && (
                        <div className="text-xs">
                            <span className="font-semibold">Condition Result:</span>{" "}
                            <span className={data.conditionResult ? "font-bold text-(--color-success-wMain)" : "font-bold text-(--color-warning-wMain)"}>{data.conditionResult ? "True" : "False"}</span>
                        </div>
                    )}
                    {data.metadata?.condition && (
                        <div>
                            <div className="mb-1 text-xs font-semibold">Condition:</div>
                            <code className="bg-muted/50 block rounded-md p-2 text-xs break-all">{data.metadata.condition}</code>
                        </div>
                    )}
                    {data.errorMessage && (
                        <div className="text-destructive text-xs">
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
                <h4 className="mb-2 text-sm font-semibold">Workflow Start</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Workflow:</span> {data.workflowName}
                    </div>
                    {data.workflowInput && (
                        <div>
                            <div className="mb-2 text-xs font-semibold">Input:</div>
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
                <h4 className="mb-2 text-sm font-semibold">Workflow Result</h4>
                <div className="space-y-2">
                    <div className="text-xs">
                        <span className="font-semibold">Status:</span> <span className={data.status === "success" ? "text-(--color-success-wMain)" : "text-red-600 dark:text-red-400"}>{data.status}</span>
                    </div>
                    {data.workflowOutput && (
                        <div>
                            <div className="mb-2 text-xs font-semibold">Output:</div>
                            {renderFormattedArguments(data.workflowOutput)}
                        </div>
                    )}
                    {data.errorMessage && (
                        <div className="text-xs text-red-600 dark:text-red-400">
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
            <div className="mt-4 border-t pt-4">
                <div className="mb-2 flex min-w-0 items-baseline gap-1 text-xs font-semibold">
                    <span className="flex-shrink-0">Output Artifact:</span>
                    <span className="text-secondary-foreground min-w-0 truncate font-normal" title={outputArtifactRef.name}>
                        {outputArtifactRef.name}
                    </span>
                    {outputArtifactRef.version !== undefined && <span className="ml-1 flex-shrink-0 text-purple-600 dark:text-purple-400">v{outputArtifactRef.version}</span>}
                </div>
                <div className="rounded-md border p-2">
                    <ArtifactContentViewer name={outputArtifactRef.name} version={outputArtifactRef.version} />
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
            <div className={asColumn ? "" : "mt-4 border-t pt-4"}>
                <div className={`flex items-center gap-2 ${asColumn ? "mb-3 border-b pb-2" : "mb-3"}`}>
                    <div className={`${asColumn ? "h-2 w-2 rounded-full bg-indigo-500" : ""}`}></div>
                    <FileText className={`h-4 w-4 text-indigo-500 dark:text-indigo-400 ${asColumn ? "hidden" : ""}`} />
                    <h4 className="text-sm font-bold text-indigo-600 dark:text-indigo-400">{asColumn ? "CREATED ARTIFACTS" : `Created Artifacts (${nodeDetails.createdArtifacts.length})`}</h4>
                </div>
                <div className="space-y-3">
                    {nodeDetails.createdArtifacts.map((artifact, index) => (
                        <div key={`${artifact.filename}-${artifact.version ?? index}`} className="rounded-md border border-indigo-200 bg-indigo-50 p-3 dark:border-indigo-700 dark:bg-indigo-900/30">
                            <div className="mb-1 flex items-center justify-between gap-2">
                                <button
                                    onClick={() => handleArtifactClick(artifact.filename, artifact.version)}
                                    className="min-w-0 cursor-pointer truncate text-sm font-semibold text-indigo-700 transition-colors hover:text-indigo-900 hover:underline dark:text-indigo-300 dark:hover:text-indigo-100"
                                    title={artifact.filename}
                                >
                                    {artifact.filename}
                                </button>
                                <div className="flex flex-shrink-0 items-center">
                                    {artifact.version !== undefined && <span className="rounded bg-indigo-200 px-1.5 py-0.5 text-xs text-indigo-700 dark:bg-indigo-800 dark:text-indigo-300">v{artifact.version}</span>}
                                </div>
                            </div>
                            {artifact.description && <p className="mb-2 text-xs">{artifact.description}</p>}
                            {artifact.mimeType && (
                                <div className="text-secondary-foreground text-xs">
                                    <span className="font-medium">Type:</span> {artifact.mimeType}
                                </div>
                            )}
                            <div className="bg-card mt-2 rounded-lg p-2">
                                <ArtifactContentViewer name={artifact.filename} version={artifact.version} mimeType={artifact.mimeType} />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    // Render the main node details content
    const renderMainContent = () => (
        <div className="flex flex-col">
            {/* Header */}
            <div className="dark:bg-card flex flex-shrink-0 items-center gap-3 border-b p-4">
                {getNodeIcon()}
                <div className="min-w-0 flex-1">
                    <h3 className="truncate text-base font-bold">{nodeDetails.label}</h3>
                    {nodeDetails.description ? (
                        <p className="text-secondary-foreground truncate text-xs" title={nodeDetails.description}>
                            {nodeDetails.description}
                        </p>
                    ) : (
                        <p className="text-secondary-foreground text-xs capitalize">{nodeDetails.nodeType} Node</p>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="min-h-0 flex-1 overflow-hidden">
                {hasRequestAndResult ? (
                    /* Split view for request and result (and optionally created artifacts) */
                    <div className={`grid h-full grid-cols-1 ${hasCreatedArtifacts ? "lg:grid-cols-3" : "lg:grid-cols-2"} divide-y divide-gray-200 lg:divide-x lg:divide-y-0 dark:divide-gray-700`}>
                        {/* Request Column */}
                        <div className="max-h-[calc(85vh-140px)] overflow-y-auto p-4">
                            <ColumnHeader label="REQUEST" color="(--color-info-wMain)" />
                            {renderStepContent(nodeDetails.requestStep, true)}
                        </div>

                        {/* Result Column */}
                        <div className="max-h-[calc(85vh-140px)] overflow-y-auto p-4">
                            <ColumnHeader label="RESULT" color="(--color-success-wMain)" />
                            {renderStepContent(nodeDetails.resultStep, false)}
                            {renderOutputArtifact()}
                        </div>

                        {/* Created Artifacts Column (when present) */}
                        {hasCreatedArtifacts && <div className="max-h-[calc(85vh-140px)] overflow-y-auto p-4">{renderCreatedArtifacts(true)}</div>}
                    </div>
                ) : (
                    /* Single view when only request or result is available */
                    <div className="max-h-[calc(85vh-140px)] overflow-y-auto p-4">
                        {nodeDetails.requestStep && (
                            <div className="mb-4">
                                <div className="mb-3 flex items-center gap-2 border-b pb-2">
                                    <div className="h-2 w-2 rounded-full bg-(--color-info-wMain)"></div>
                                    <h4 className="text-sm font-bold text-(--color-info-wMain)">REQUEST</h4>
                                </div>
                                {renderStepContent(nodeDetails.requestStep, true)}
                            </div>
                        )}
                        {nodeDetails.resultStep && (
                            <div>
                                <div className="mb-3 flex items-center gap-2 border-b pb-2">
                                    <div className="h-2 w-2 rounded-full bg-(--color-success-wMain)"></div>
                                    <h4 className="text-sm font-bold text-(--color-success-wMain)">RESULT</h4>
                                </div>
                                {renderStepContent(nodeDetails.resultStep, false)}
                                {renderOutputArtifact()}
                                {renderCreatedArtifacts()}
                            </div>
                        )}
                        {!nodeDetails.requestStep && !nodeDetails.resultStep && <div className="text-muted-foreground flex h-32 items-center justify-center italic">No detailed information available for this node</div>}
                    </div>
                )}
            </div>
        </div>
    );

    return renderMainContent();
};

export default NodeDetailsCard;
