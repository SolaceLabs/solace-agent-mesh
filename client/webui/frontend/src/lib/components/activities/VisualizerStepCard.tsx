import { useState, type FC, type ReactNode, type MouseEvent } from "react";

import { CheckCircle, ExternalLink, FileText, GitCommit, GitMerge, HardDrive, Link, List, MessageSquare, Share2, Split, Terminal, User, Workflow, XCircle, Zap } from "lucide-react";

import { JSONViewer, MarkdownHTMLConverter } from "@/lib/components";
import { useChatContext } from "@/lib/hooks";
import { ImageSearchGrid } from "@/lib/components/research";
import type {
    ArtifactNotificationData,
    LLMCallData,
    LLMResponseToAgentData,
    ToolDecisionData,
    ToolInvocationStartData,
    ToolResultData,
    VisualizerStep,
    WorkflowExecutionResultData,
    WorkflowExecutionStartData,
    WorkflowNodeExecutionResultData,
    WorkflowNodeExecutionStartData,
} from "@/lib/types";
import { isString } from "@/lib/utils";

interface VisualizerStepCardProps {
    step: VisualizerStep;
    isHighlighted?: boolean;
    onClick?: () => void;
    variant?: "list" | "popover";
}

const VisualizerStepCard: FC<VisualizerStepCardProps> = ({ step, isHighlighted, onClick, variant = "list" }) => {
    const { artifacts, setPreviewArtifact, setActiveSidePanelTab, setIsSidePanelCollapsed, navigateArtifactVersion } = useChatContext();

    const getStepIcon = () => {
        switch (step.type) {
            case "USER_REQUEST":
                return <User className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
            case "AGENT_RESPONSE_TEXT":
                return <Zap className="mr-2 text-teal-500 dark:text-teal-400" size={18} />;
            case "TASK_COMPLETED":
                return <CheckCircle className="mr-2 text-green-500 dark:text-green-400" size={18} />;
            case "TASK_FAILED":
                return <XCircle className="mr-2 text-red-500 dark:text-red-400" size={18} />;
            case "AGENT_LLM_CALL":
                return <Zap className="mr-2 text-purple-500 dark:text-purple-400" size={18} />;
            case "AGENT_LLM_RESPONSE_TO_AGENT":
                return <Zap className="mr-2 text-teal-500 dark:text-teal-400" size={18} />;
            case "AGENT_LLM_RESPONSE_TOOL_DECISION": {
                const firstDecision = step.data.toolDecision?.decisions?.[0];
                const isPeer = firstDecision?.isPeerDelegation;

                return isPeer ? <Share2 className="mr-2 text-orange-500 dark:text-orange-400" size={18} /> : <Terminal className="mr-2 text-orange-500 dark:text-orange-400" size={18} />;
            }
            case "AGENT_TOOL_INVOCATION_START":
                return step.data.toolInvocationStart?.isPeerInvocation ? <Share2 className="mr-2 text-cyan-500 dark:text-cyan-400" size={18} /> : <Terminal className="mr-2 text-cyan-500 dark:text-cyan-400" size={18} />;
            case "AGENT_TOOL_EXECUTION_RESULT":
                return <HardDrive className="mr-2 text-teal-500 dark:text-teal-400" size={18} />;
            case "AGENT_ARTIFACT_NOTIFICATION":
                return <FileText className="mr-2 text-indigo-500 dark:text-indigo-400" size={18} />;
            case "WORKFLOW_EXECUTION_START":
            case "WORKFLOW_EXECUTION_RESULT":
                return <Workflow className="mr-2 text-purple-500 dark:text-purple-400" size={18} />;
            case "WORKFLOW_NODE_EXECUTION_START":
                if (step.data.workflowNodeExecutionStart?.nodeType === "map") return <List className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
                if (step.data.workflowNodeExecutionStart?.nodeType === "fork") return <Split className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
                if (step.data.workflowNodeExecutionStart?.nodeType === "switch") return <GitMerge className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
                return <GitCommit className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
            case "WORKFLOW_NODE_EXECUTION_RESULT":
                return <GitCommit className="mr-2 text-green-500 dark:text-green-400" size={18} />;
            case "WORKFLOW_MAP_PROGRESS":
                return <List className="mr-2 text-blue-500 dark:text-blue-400" size={18} />;
            default:
                return <MessageSquare className="mr-2 text-gray-500 dark:text-gray-400" size={18} />;
        }
    };

    const formattedTimestamp = new Date(step.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
    const milliseconds = String(new Date(step.timestamp).getMilliseconds()).padStart(3, "0");
    const displayTimestamp = `${formattedTimestamp}.${milliseconds}`;

    const renderLLMCallData = (data: LLMCallData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <p>
                <strong>Model:</strong> {data.modelName}
            </p>
            <p className="mt-1">
                <strong>Prompt Preview:</strong>
            </p>
            <pre className="max-h-28 overflow-y-auto rounded bg-gray-100 p-1.5 font-mono text-xs break-all whitespace-pre-wrap dark:bg-gray-700">{data.promptPreview}</pre>
        </div>
    );

    const LLMResponseToAgentDetails: FC<{ data: LLMResponseToAgentData }> = ({ data }) => {
        const [expanded, setExpanded] = useState(false);

        const toggleExpand = (e: MouseEvent) => {
            e.stopPropagation();
            setExpanded(!expanded);
        };

        // If not expanded, just show a minimal summary
        if (!expanded) {
            return (
                <div className="mt-1.5 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                    <span className="italic">Internal LLM response</span>
                    <button onClick={toggleExpand} className="text-xs text-blue-500 underline hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
                        Show details
                    </button>
                </div>
            );
        }

        // Expanded view
        return (
            <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                <div className="mb-1 flex items-center justify-between">
                    <strong>LLM Response Details:</strong>
                    <button onClick={toggleExpand} className="text-xs text-blue-500 underline hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">
                        Hide details
                    </button>
                </div>
                {data.modelName && (
                    <p>
                        <strong>Model:</strong> {data.modelName}
                    </p>
                )}
                <div className="mt-1">
                    <p>
                        <strong>Response Preview:</strong>
                    </p>
                    <pre className="max-h-28 overflow-y-auto rounded bg-gray-100 p-1.5 font-mono text-xs break-all whitespace-pre-wrap dark:bg-gray-700">{data.responsePreview}</pre>
                </div>
                {data.isFinalResponse !== undefined && (
                    <p className="mt-1">
                        <strong>Final Response:</strong> {data.isFinalResponse ? "Yes" : "No"}
                    </p>
                )}
            </div>
        );
    };

    const renderToolDecisionData = (data: ToolDecisionData) => (
        <div className="mt-1.5 rounded-md bg-blue-50 p-2 font-mono text-xs text-blue-700 dark:bg-blue-900 dark:text-blue-300">
            <p className="mb-2">
                <strong>🔧 {data.isParallel ? "Parallel Tool Calls:" : "Tool Call:"}</strong>
            </p>
            <ul className="space-y-1 pl-2">
                {data.decisions.map(decision => (
                    <li key={decision.functionCallId} className="flex items-center">
                        <span className="mr-2">•</span>
                        <code>{decision.toolName}</code>
                    </li>
                ))}
            </ul>
        </div>
    );

    const renderToolInvocationStartData = (data: ToolInvocationStartData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <p>
                <strong>Tool:</strong> {data.toolName}
            </p>
            <p className="mt-1">
                <strong>Arguments:</strong>
            </p>
            <div className="max-h-40 overflow-y-auto rounded bg-gray-100 p-1.5 dark:bg-gray-700">
                <JSONViewer data={data.toolArguments} />
            </div>
        </div>
    );

    /**
     * Renders result data as either a JSON viewer (for objects) or a preformatted text block (for primitives).
     * Abstracts the common pattern of displaying tool result data.
     */
    const renderResultData = (resultData: unknown): ReactNode => {
        if (typeof resultData === "object") {
            // Cast is safe here as JSONViewer handles null and object types
            return <JSONViewer data={resultData as Parameters<typeof JSONViewer>[0]["data"]} />;
        }
        return <pre className="font-mono text-xs break-all whitespace-pre-wrap">{String(resultData)}</pre>;
    };

    const renderToolResultData = (data: ToolResultData) => {
        // Check if this is a web search result with images
        let parsedResult = null;
        let hasImages = false;

        try {
            // Try to parse the result if it's a string
            if (isString(data.resultData)) {
                parsedResult = JSON.parse(data.resultData);
            } else if (typeof data.resultData === "object") {
                parsedResult = data.resultData;
            }

            // Check if the result has an images array (from web search tools)
            if (parsedResult?.result) {
                const innerResult = isString(parsedResult.result) ? JSON.parse(parsedResult.result) : parsedResult.result;

                if (innerResult?.images && Array.isArray(innerResult.images) && innerResult.images.length > 0) {
                    hasImages = true;
                }
            }
        } catch {
            // Not JSON or parsing failed, will display as normal
        }

        return (
            <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                <p>
                    <strong>Tool:</strong> {data.toolName}
                </p>

                {hasImages && parsedResult?.result ? (
                    <>
                        <p className="mt-1">
                            <strong>Image Results:</strong>
                        </p>
                        <ImageSearchGrid images={isString(parsedResult.result) ? JSON.parse(parsedResult.result).images : parsedResult.result.images} />
                        <details className="mt-2">
                            <summary className="cursor-pointer text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300">Show full result data</summary>
                            <div className="mt-2 max-h-40 overflow-y-auto rounded bg-gray-100 p-1.5 dark:bg-gray-700">{renderResultData(data.resultData)}</div>
                        </details>
                    </>
                ) : (
                    <>
                        <p className="mt-1">
                            <strong>Result:</strong>
                        </p>
                        <div className="max-h-40 overflow-y-auto rounded bg-gray-100 p-1.5 dark:bg-gray-700">{renderResultData(data.resultData)}</div>
                    </>
                )}
            </div>
        );
    };
    const renderArtifactNotificationData = (data: ArtifactNotificationData) => {
        const handleViewFile = async (e: MouseEvent) => {
            e.stopPropagation();

            // Find the artifact by filename
            const artifact = artifacts.find(a => a.filename === data.artifactName);

            if (artifact) {
                // Switch to Files tab
                setActiveSidePanelTab("files");

                // Expand side panel if collapsed
                setIsSidePanelCollapsed(false);

                // Set preview artifact to open the file (loads latest by default)
                setPreviewArtifact(artifact);

                // If a specific version is indicated in the workflow data, navigate to it
                if (data.version !== undefined && data.version !== artifact.version) {
                    // Wait a bit for the file to load, then navigate to the specific version
                    setTimeout(() => {
                        navigateArtifactVersion(artifact.filename, data.version!);
                    }, 100);
                }
            }
            // If artifact not found, do nothing (silent failure)
        };

        return (
            <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                <div className="flex items-center justify-between">
                    <p>
                        <strong>Artifact:</strong> {data.artifactName}
                        {data.version !== undefined && <span className="text-gray-500 dark:text-gray-400"> (v{data.version})</span>}
                    </p>
                    <button onClick={handleViewFile} className="flex items-center gap-1 text-blue-600 transition-colors hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300" title="View in Files tab">
                        <span className="text-xs">View File</span>
                        <ExternalLink size={12} />
                    </button>
                </div>
                {data.mimeType && (
                    <p>
                        <strong>Type:</strong> {data.mimeType}
                    </p>
                )}
                {data.description && (
                    <p className="mt-1">
                        <strong>Description:</strong> {data.description}
                    </p>
                )}
            </div>
        );
    };

    const renderWorkflowNodeStartData = (data: WorkflowNodeExecutionStartData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <div className="mb-1 flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase text-gray-500 dark:text-gray-400">{data.nodeType} Node</span>
                {(data.iterationIndex !== undefined && data.iterationIndex !== null && typeof data.iterationIndex === 'number') && <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-800 dark:bg-blue-900 dark:text-blue-200">Iter #{data.iterationIndex}</span>}
            </div>

            {data.condition && (
                <div className="mt-1">
                    <p className="mb-0.5 font-semibold">Condition:</p>
                    <code className="block break-all rounded border border-gray-200 bg-gray-100 p-1.5 font-mono text-xs dark:border-gray-600 dark:bg-gray-800">{data.condition}</code>
                </div>
            )}
            {data.trueBranch && (
                <p className="mt-1">
                    <strong>True Branch:</strong> {data.trueBranch}
                </p>
            )}
            {data.falseBranch && (
                <p>
                    <strong>False Branch:</strong> {data.falseBranch}
                </p>
            )}
        </div>
    );

    const renderWorkflowNodeResultData = (data: WorkflowNodeExecutionResultData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <p>
                <strong>Status:</strong> {data.status}
            </p>
            {data.metadata?.condition && (
                <div className="mt-1 mb-1">
                    <p className="mb-0.5 font-semibold">Condition:</p>
                    <code className="block break-all rounded border border-gray-200 bg-gray-100 p-1.5 font-mono text-xs dark:border-gray-600 dark:bg-gray-800">{data.metadata.condition}</code>
                </div>
            )}
            {data.metadata?.condition_result !== undefined && (
                <p className="mt-1">
                    <strong>Condition Result:</strong> <span className={data.metadata.condition_result ? "font-bold text-green-600 dark:text-green-400" : "font-bold text-orange-600 dark:text-orange-400"}>{data.metadata.condition_result ? "True" : "False"}</span>
                </p>
            )}
            {data.outputArtifactRef && (
                <p className="mt-1">
                    <strong>Output:</strong> {data.outputArtifactRef.name} (v{data.outputArtifactRef.version})
                </p>
            )}
            {data.errorMessage && (
                <p className="mt-1 text-red-600">
                    <strong>Error:</strong> {data.errorMessage}
                </p>
            )}
        </div>
    );

    const renderWorkflowExecutionStartData = (data: WorkflowExecutionStartData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <p>
                <strong>Workflow:</strong> {data.workflowName}
            </p>
            {data.workflowInput && (
                <div className="mt-1">
                    <p>
                        <strong>Input:</strong>
                    </p>
                    <div className="max-h-40 overflow-y-auto rounded bg-gray-100 p-1.5 dark:bg-gray-800">
                        <JSONViewer data={data.workflowInput} />
                    </div>
                </div>
            )}
        </div>
    );

    const renderWorkflowExecutionResultData = (data: WorkflowExecutionResultData) => (
        <div className="mt-1.5 rounded-md bg-gray-50 p-2 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-300">
            <p>
                <strong>Status:</strong> {data.status}
            </p>
            {data.workflowOutput && (
                <div className="mt-1">
                    <p>
                        <strong>Output:</strong>
                    </p>
                    <div className="max-h-60 overflow-y-auto rounded bg-gray-100 p-1.5 dark:bg-gray-800">
                        <JSONViewer data={data.workflowOutput} />
                    </div>
                </div>
            )}
            {data.errorMessage && (
                <p className="text-red-600">
                    <strong>Error:</strong> {data.errorMessage}
                </p>
            )}
        </div>
    );

    // Calculate indentation based on nesting level - only apply in list variant
    const indentationStyle =
        variant === "list" && step.nestingLevel && step.nestingLevel > 0
            ? { marginLeft: `${step.nestingLevel * 24}px` } // e.g., 24px per level
            : {};

    // Different styling based on variant
    const cardClasses =
        variant === "popover"
            ? `
      p-3 bg-transparent hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors duration-150
      ${onClick ? "cursor-pointer" : ""}
    `
            : `
      mb-3 p-3 border rounded-lg shadow-sm
      bg-white dark:bg-gray-800 hover:shadow-md transition-shadow duration-150
      ${isHighlighted ? "border-blue-500 dark:border-blue-400 ring-2 ring-blue-500 dark:ring-blue-400" : "border-gray-200 dark:border-gray-700"}
      ${onClick ? "cursor-pointer" : ""}
    `;

    const getDelegationText = () => {
        if (step.type === "AGENT_LLM_RESPONSE_TOOL_DECISION" || step.type === "AGENT_TOOL_INVOCATION_START") {
            return "Delegated to: ";
        }
        if (step.type === "AGENT_TOOL_EXECUTION_RESULT") {
            return "Response from: ";
        }
        return "Peer Interaction with: ";
    };

    return (
        <div className={cardClasses} style={indentationStyle} onClick={onClick}>
            <div className="mb-1.5 flex w-full items-center gap-1">
                {getStepIcon()}
                <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-2">
                    <h4 className="flex-1 truncate text-sm font-semibold" title={step.title}>
                        {step.title}
                    </h4>
                    <span className="text-muted-foreground shrink-0 font-mono text-xs">{displayTimestamp}</span>
                </div>
            </div>
            {step.delegationInfo && step.delegationInfo.length > 0 && (
                <div className="mt-2 mb-1.5 space-y-2 rounded-r-md border-l-4 border-blue-500 bg-blue-50 p-2 text-sm dark:border-blue-400 dark:bg-gray-700/60">
                    {step.delegationInfo.map(info => (
                        <div key={info.functionCallId}>
                            <div className="flex items-center font-semibold text-blue-700 dark:text-blue-300">
                                <Link className="mr-2 h-4 w-4 flex-shrink-0" />
                                <span>
                                    {getDelegationText()}
                                    {info.peerAgentName}
                                </span>
                            </div>
                            {info.subTaskId && (
                                <div className="mt-0.5 ml-[24px] text-xs text-blue-600 dark:text-blue-400">
                                    Sub-Task:{" "}
                                    <span className="font-mono" title={info.subTaskId}>
                                        {info.subTaskId.substring(0, 15)}...
                                    </span>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
            {step.data.text && (
                <div className="max-h-20 overflow-y-auto pl-1 text-sm text-gray-800 dark:text-gray-100">
                    <MarkdownHTMLConverter>{step.data.text}</MarkdownHTMLConverter>
                </div>
            )}
            {step.data.finalMessage && (
                <div className="pl-1 text-sm text-gray-800 dark:text-gray-100">
                    <MarkdownHTMLConverter>{step.data.finalMessage}</MarkdownHTMLConverter>
                </div>
            )}
            {step.type === "TASK_COMPLETED" && !step.data.finalMessage && <div className="pl-1 text-sm text-gray-600 italic dark:text-gray-300">Task completed successfully.</div>}
            {step.data.errorDetails && (
                <div className="mt-1 rounded-md bg-red-50 p-2 pl-1 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-400">
                    <p>
                        <strong>Error:</strong> {step.data.errorDetails.message}
                    </p>
                    {step.data.errorDetails.code && <p className="text-xs">Code: {step.data.errorDetails.code}</p>}
                </div>
            )}
            {step.data.llmCall && renderLLMCallData(step.data.llmCall)}
            {step.data.llmResponseToAgent && <LLMResponseToAgentDetails data={step.data.llmResponseToAgent} />}
            {step.data.toolDecision && renderToolDecisionData(step.data.toolDecision)}
            {step.data.toolInvocationStart && renderToolInvocationStartData(step.data.toolInvocationStart)}
            {step.data.toolResult && renderToolResultData(step.data.toolResult)}
            {step.data.artifactNotification && renderArtifactNotificationData(step.data.artifactNotification)}
            {step.data.workflowExecutionStart && renderWorkflowExecutionStartData(step.data.workflowExecutionStart)}
            {step.data.workflowNodeExecutionStart && renderWorkflowNodeStartData(step.data.workflowNodeExecutionStart)}
            {step.data.workflowNodeExecutionResult && renderWorkflowNodeResultData(step.data.workflowNodeExecutionResult)}
            {step.data.workflowExecutionResult && renderWorkflowExecutionResultData(step.data.workflowExecutionResult)}
        </div>
    );
};

export { VisualizerStepCard };
