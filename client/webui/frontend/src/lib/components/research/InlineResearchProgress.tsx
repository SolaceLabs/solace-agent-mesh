/**
 * Inline Research Progress Component
 *
 * Displays research stages building inline as they progress.
 * Each stage appears as a card that shows its status and details.
 */

import React from 'react';
import { Search, Brain, FileText, Loader2, Database, Globe } from 'lucide-react';

export interface ResearchProgressData {
  type: 'deep_research_progress';
  phase: 'planning' | 'searching' | 'analyzing' | 'writing';
  status_text: string;
  progress_percentage: number;
  current_iteration: number;
  total_iterations: number;
  sources_found: number;
  current_query: string;
  fetching_urls: Array<{url: string; title: string; favicon: string; source_type?: string}>;
  elapsed_seconds: number;
  max_runtime_seconds: number;
}

interface InlineResearchProgressProps {
  progress: ResearchProgressData;
  isComplete?: boolean;
  onClick?: () => void;
}

interface StageInfo {
  phase: 'planning' | 'searching' | 'analyzing' | 'writing';
  icon: typeof Brain;
  label: string;
  description: string;
}

const stages: StageInfo[] = [
  {
    phase: 'planning',
    icon: Brain,
    label: 'Starting research',
    description: 'Planning research strategy',
  },
  {
    phase: 'searching',
    icon: Search,
    label: 'Exploring sources',
    description: 'Searching for relevant information',
  },
  {
    phase: 'analyzing',
    icon: Brain,
    label: 'Analyzing content',
    description: 'Processing and analyzing sources',
  },
  {
    phase: 'writing',
    icon: FileText,
    label: 'Generating report',
    description: 'Compiling final research',
  },
];

const getStageStatus = (
  stagePhase: string,
  currentPhase: string,
  isComplete: boolean
): 'pending' | 'active' | 'complete' => {
  const phaseOrder = ['planning', 'searching', 'analyzing', 'writing'];
  const stageIndex = phaseOrder.indexOf(stagePhase);
  const currentIndex = phaseOrder.indexOf(currentPhase);

  if (isComplete && stagePhase === 'writing') return 'complete';
  if (stageIndex < currentIndex) return 'complete';
  if (stageIndex === currentIndex) return 'active';
  return 'pending';
};

export const InlineResearchProgress: React.FC<InlineResearchProgressProps> = ({
  progress,
  isComplete = false,
  onClick,
}) => {
  return (
    <div className="space-y-3 my-4">
      {stages.map((stage) => {
        const status = getStageStatus(stage.phase, progress.phase, isComplete);
        const Icon = stage.icon;
        const isCurrentStage = progress.phase === stage.phase;
        
        // Only show the currently active stage (hide completed and pending)
        if (status !== 'active') return null;

        return (
          <div key={stage.phase}>
            <div
              onClick={onClick}
              className="rounded-xl border transition-all duration-300 bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-700 shadow-sm cursor-pointer hover:border-primary"
            >
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* Icon */}
                    <div className="flex-shrink-0 mt-0.5 text-primary">
                      <Icon className="h-5 w-5 animate-pulse" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm">
                        {stage.label}
                      </h3>

                      {/* Progress bar for active stage - moved up below title */}
                      {isCurrentStage && (
                        <div className="mt-2">
                          <div className="h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300 ease-out"
                              style={{ width: `${Math.min(progress.progress_percentage, 100)}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Status text for active stage */}
                      {isCurrentStage && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {progress.status_text}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Progress indicator */}
                  <div className="flex-shrink-0">
                    <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                  </div>
                </div>
              </div>
            </div>

            {/* Fetching URLs - moved below the box */}
            {isCurrentStage && progress.fetching_urls && progress.fetching_urls.length > 0 && (
              <div className="mt-2 ml-1 space-y-1">
                {progress.fetching_urls.slice(0, 3).map((urlInfo, idx) => {
                  // Determine which icon to show based on source type
                  const getSourceIcon = () => {
                    const sourceType = urlInfo.source_type;
                    if (!sourceType || sourceType === 'web') {
                      // Web source - use favicon if available
                      if (urlInfo.favicon && urlInfo.favicon.trim() !== '') {
                        return (
                          <img
                            src={urlInfo.favicon}
                            alt=""
                            className="w-3 h-3 flex-shrink-0"
                            onError={(e) => { e.currentTarget.style.display = 'none'; }}
                          />
                        );
                      }
                      return <Globe className="w-3 h-3 flex-shrink-0" />;
                    }
                    
                    // Web-only version - only web and kb sources
                    switch (sourceType) {
                      case 'kb':
                        return <Database className="w-3 h-3 flex-shrink-0" />;
                      default:
                        return <Globe className="w-3 h-3 flex-shrink-0" />;
                    }
                  };

                  return (
                    <div
                      key={idx}
                      className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400"
                    >
                      {getSourceIcon()}
                      <span className="truncate" title={urlInfo.title}>
                        {urlInfo.title}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default InlineResearchProgress;