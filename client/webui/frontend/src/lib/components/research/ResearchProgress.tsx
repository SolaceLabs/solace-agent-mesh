/**
 * Research Progress Component
 *
 * Displays real-time progress updates during deep research operations.
 * Shows current iteration, phase, sources found, and progress percentage.
 */

import React from "react";
import { Progress } from "../ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Search, Brain, FileText, CheckCircle } from "lucide-react";

export interface ResearchProgressData {
    type: "deep_research_progress";
    phase: "planning" | "searching" | "analyzing" | "writing";
    status_text: string;
    progress_percentage: number;
    current_iteration: number;
    total_iterations: number;
    sources_found: number;
    current_query: string;
    fetching_urls: Array<{ url: string; title: string; favicon: string }>;
    elapsed_seconds: number;
    max_runtime_seconds: number;
}

interface ResearchProgressProps {
    progress: ResearchProgressData;
    isComplete?: boolean;
}

const phaseIcons = {
    planning: Brain,
    searching: Search,
    analyzing: Brain,
    writing: FileText,
};

const phaseLabels = {
    planning: "Planning Research",
    searching: "Searching Sources",
    analyzing: "Analyzing Sources",
    writing: "Generating Report",
};

const phaseColors = {
    planning: "bg-primary",
    searching: "bg-primary",
    analyzing: "bg-primary",
    writing: "bg-primary",
};

export const ResearchProgress: React.FC<ResearchProgressProps> = ({ progress, isComplete = false }) => {
    const PhaseIcon = phaseIcons[progress.phase];
    const phaseLabel = phaseLabels[progress.phase];
    const phaseColor = phaseColors[progress.phase];

    return (
        <Card className="dark:bg-card w-full bg-gray-50">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-lg">
                        {isComplete ? (
                            <>
                                <CheckCircle className="h-5 w-5 text-green-500" />
                                <span>Research Complete</span>
                            </>
                        ) : (
                            <>
                                <PhaseIcon className="h-5 w-5 animate-pulse" />
                                <span>Deep Research in Progress</span>
                            </>
                        )}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline">
                            Iteration {progress.current_iteration}/{progress.total_iterations}
                        </Badge>
                        {progress.sources_found > 0 && <Badge variant="secondary">{progress.sources_found} Sources</Badge>}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Progress Bar */}
                <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">{phaseLabel}</span>
                        <span className="font-medium">{Math.round(progress.progress_percentage)}%</span>
                    </div>
                    <Progress value={progress.progress_percentage} className="h-2" />
                </div>

                {/* Phase Steps */}
                <div className="grid grid-cols-4 gap-2 pt-2">
                    {(["planning", "searching", "analyzing", "writing"] as const).map((phase, idx) => {
                        const Icon = phaseIcons[phase];
                        const isActive = progress.phase === phase;
                        const phaseOrder = ["planning", "searching", "analyzing", "writing"];
                        const isComplete = idx < phaseOrder.indexOf(progress.phase);

                        return (
                            <div
                                key={phase}
                                className={`flex flex-col items-center gap-1 rounded-lg p-2 transition-colors ${
                                    isActive ? "bg-primary/10 border-primary border" : isComplete ? "border border-green-500/30 bg-green-500/10 dark:border-green-500/40 dark:bg-green-500/20" : "bg-muted"
                                }`}
                            >
                                <Icon className={`h-4 w-4 ${isActive ? "text-primary animate-pulse" : isComplete ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`} />
                                <span className="text-center text-xs capitalize">{phase}</span>
                            </div>
                        );
                    })}
                </div>

                {/* Phase Indicator */}
                <div className="flex items-center gap-2">
                    <div className={`h-2 w-2 rounded-full ${phaseColor} animate-pulse`} />
                    <span className="text-muted-foreground text-sm">{progress.status_text}</span>
                </div>

                {/* Current Query */}
                {progress.current_query && (
                    <div className="bg-muted/50 rounded-lg p-3">
                        <div className="text-muted-foreground mb-1 text-xs font-medium">Current Query</div>
                        <div className="text-sm">{progress.current_query}</div>
                    </div>
                )}

                {/* Fetching URLs with Favicons */}
                {progress.fetching_urls && progress.fetching_urls.length > 0 && (
                    <div className="space-y-2">
                        <div className="text-muted-foreground text-xs font-medium">Reading Pages</div>
                        <div className="space-y-1">
                            {progress.fetching_urls.map((urlInfo, idx) => (
                                <div key={idx} className="bg-muted/30 flex items-center gap-2 rounded p-2 text-sm">
                                    {urlInfo.favicon && (
                                        <img
                                            src={urlInfo.favicon}
                                            alt=""
                                            className="h-4 w-4 flex-shrink-0"
                                            onError={e => {
                                                e.currentTarget.style.display = "none";
                                            }}
                                        />
                                    )}
                                    <span className="flex-1 truncate" title={urlInfo.title}>
                                        {urlInfo.title}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Time Tracking */}
                {progress.max_runtime_seconds > 0 && (
                    <div className="text-muted-foreground flex items-center justify-between text-xs">
                        <span>
                            Elapsed: {Math.floor(progress.elapsed_seconds / 60)}m {progress.elapsed_seconds % 60}s
                        </span>
                        <span>Limit: {Math.floor(progress.max_runtime_seconds / 60)}m</span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default ResearchProgress;
