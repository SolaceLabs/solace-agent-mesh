/**
 * Deep Research Toggle Component
 *
 * Provides a toggle button to enable/disable deep research mode.
 * Shows visual indicator when active and hides when deep research is not available.
 */

import React from 'react';
import { Microscope, Settings } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/lib/components/ui/tooltip';
import type { AgentCardInfo } from '@/lib/types';
import type { DeepResearchSettings } from './deepResearchSettings.ts';

interface DeepResearchToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  disabled?: boolean;
  agents: AgentCardInfo[];
  settings: DeepResearchSettings;
  onSettingsClick?: () => void;
}

export const DeepResearchToggle: React.FC<DeepResearchToggleProps> = ({
  enabled,
  onToggle,
  disabled,
  agents,
  onSettingsClick
}) => {
  // Find agent with deep_research skill
  const deepResearchAgent = agents.find(
    a => a.skills?.some(s => s.id === 'deep_research')
  );
  
  if (!deepResearchAgent) return null;
  
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => onToggle(!enabled)}
          disabled={disabled}
          className={`
            inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
            text-xs font-medium transition-all
            ${enabled
              ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
            }
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
          aria-label={enabled
            ? 'Deep Research enabled - Click to disable'
            : 'Enable Deep Research'
          }
        >
          <Microscope className="h-3.5 w-3.5" />
          <span>Deep Research</span>
          {enabled && onSettingsClick && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className="cursor-pointer hover:opacity-75"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSettingsClick();
                  }}
                  aria-label="Configure settings"
                >
                  <Settings className="h-3 w-3" />
                </span>
              </TooltipTrigger>
              <TooltipContent>Configure settings</TooltipContent>
            </Tooltip>
          )}
        </button>
      </TooltipTrigger>
      <TooltipContent>
        {enabled
          ? 'Deep Research enabled - Click to disable'
          : 'Enable Deep Research'
        }
      </TooltipContent>
    </Tooltip>
  );
};