/**
 * Tools Selector Component
 *
 * Provides a dropdown button to select between different research tools.
 * Currently supports Deep Research and Web Search (mutually exclusive).
 */

import React, { useState } from 'react';
import { Wrench, Microscope, Globe, Settings, AlertCircle } from 'lucide-react';
import { Button } from '@/lib/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/lib/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/lib/components/ui/tooltip';
import type { AgentCardInfo } from '@/lib/types';
import type { DeepResearchSettings } from './deepResearchSettings';

const RadioIndicator: React.FC<{ selected: boolean }> = ({ selected }) => (
  <div className="relative flex h-3.5 w-3.5 items-center justify-center">
    <div className={`h-3.5 w-3.5 rounded-full border-2 transition-colors ${
      selected
        ? 'border-blue-600 dark:border-blue-400'
        : 'border-gray-300 dark:border-gray-600'
    }`}>
      {selected && (
        <div className="absolute inset-0 m-[3px] rounded-full bg-blue-600 dark:bg-blue-400" />
      )}
    </div>
  </div>
);

interface ToolsSelectorProps {
  deepResearchEnabled: boolean;
  webSearchEnabled: boolean;
  onDeepResearchToggle: (enabled: boolean) => void;
  onWebSearchToggle: (enabled: boolean) => void;
  disabled?: boolean;
  agents: AgentCardInfo[];
  deepResearchSettings?: DeepResearchSettings;
  onDeepResearchSettingsClick?: () => void;
  webSearchConfigured?: boolean;
  deepResearchConfigured?: boolean;
}

export const ToolsSelector: React.FC<ToolsSelectorProps> = ({
  deepResearchEnabled,
  webSearchEnabled,
  onDeepResearchToggle,
  onWebSearchToggle,
  disabled,
  agents,
  onDeepResearchSettingsClick,
  webSearchConfigured = true,
  deepResearchConfigured = true
}) => {
  const [isOpen, setIsOpen] = useState(false);
  
  // Check if deep research is available
  const hasDeepResearch = agents.some(
    a => a.skills?.some(s => s.id === 'deep_research')
  );
  
  // Check if web search is available
  const hasWebSearch = agents.some(
    a => a.skills?.some(s => s.id === 'web_search')
  );
  
  // Don't show if no tools are available
  if (!hasDeepResearch && !hasWebSearch) return null;
  
  // Determine button appearance based on active tools
  const hasActiveTools = deepResearchEnabled || webSearchEnabled;
  const buttonVariant = hasActiveTools ? 'default' : 'ghost';
  
  // Handle tool selection (mutually exclusive)
  const handleDeepResearchSelect = () => {
    if (deepResearchEnabled) {
      // Deselect if already selected
      onDeepResearchToggle(false);
    } else {
      // Select deep research and deselect web search
      onDeepResearchToggle(true);
      if (webSearchEnabled) {
        onWebSearchToggle(false);
      }
    }
    // Close the dropdown after selection
    setIsOpen(false);
    
    // Focus chat input after selection
    setTimeout(() => {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('focus-chat-input'));
      }
    }, 100);
  };
  
  const handleWebSearchSelect = () => {
    if (webSearchEnabled) {
      // Deselect if already selected
      onWebSearchToggle(false);
    } else {
      // Select web search and deselect deep research
      onWebSearchToggle(true);
      if (deepResearchEnabled) {
        onDeepResearchToggle(false);
      }
    }
    // Close the dropdown after selection
    setIsOpen(false);
    
    // Focus chat input after selection
    setTimeout(() => {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('focus-chat-input'));
      }
    }, 100);
  };
  
  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant={buttonVariant}
          size="sm"
          disabled={disabled}
          className="gap-1.5"
          tooltip="Research Tools"
        >
          {deepResearchEnabled ? (
            <Microscope className="h-4 w-4" />
          ) : webSearchEnabled ? (
            <Globe className="h-4 w-4" />
          ) : (
            <Wrench className="h-4 w-4" />
          )}
          {hasActiveTools && (
            <span className="text-xs">
              {deepResearchEnabled ? 'Deep Research' : 'Web Search'}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {/* Web Search Option */}
        {hasWebSearch && (
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <div>
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    if (webSearchConfigured !== false) {
                      handleWebSearchSelect();
                    }
                  }}
                  disabled={webSearchConfigured === false}
                  className="flex items-center justify-between cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 flex-shrink-0" />
                    <div className="flex flex-col">
                      <span>Web Search</span>
                      {webSearchConfigured === false && (
                        <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />
                          Requires API keys
                        </span>
                      )}
                    </div>
                  </div>
                  <RadioIndicator selected={webSearchEnabled} />
                </DropdownMenuItem>
              </div>
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-xs">
              {webSearchConfigured === false ? (
                <p className="text-xs">Requires TAVILY_API_KEY or GOOGLE_SEARCH_API_KEY + GOOGLE_CSE_ID environment variables</p>
              ) : (
                <p className="text-xs">Search the web for current information</p>
              )}
            </TooltipContent>
          </Tooltip>
        )}
        
        {/* Deep Research Option */}
        {hasDeepResearch && (
          <>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <div>
                  <DropdownMenuItem
                    onSelect={(e) => {
                      e.preventDefault();
                      if (deepResearchConfigured !== false) {
                        handleDeepResearchSelect();
                      }
                    }}
                    disabled={deepResearchConfigured === false}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <Microscope className="h-4 w-4 flex-shrink-0" />
                      <div className="flex flex-col">
                        <span>Deep Research</span>
                        {deepResearchConfigured === false && (
                          <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                            <AlertCircle className="h-3 w-3" />
                            Requires API keys
                          </span>
                        )}
                      </div>
                    </div>
                    <RadioIndicator selected={deepResearchEnabled} />
                  </DropdownMenuItem>
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-xs">
                {deepResearchConfigured === false ? (
                  <p className="text-xs">Requires TAVILY_API_KEY or GOOGLE_SEARCH_API_KEY + GOOGLE_CSE_ID environment variables</p>
                ) : (
                  <p className="text-xs">Comprehensive iterative research across multiple sources</p>
                )}
              </TooltipContent>
            </Tooltip>
            {deepResearchEnabled && onDeepResearchSettingsClick && (
              <DropdownMenuItem
                onSelect={(e) => {
                  e.preventDefault();
                  onDeepResearchSettingsClick();
                  setIsOpen(false);
                }}
                className="flex items-center gap-2 pl-8 cursor-pointer"
              >
                <Settings className="h-3.5 w-3.5" />
                <span className="text-sm">Configure Settings</span>
              </DropdownMenuItem>
            )}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};