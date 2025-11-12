/**
 * Tools Selector Component
 *
 * Provides a dropdown button to select between different research tools.
 * Currently supports Deep Research and Web Search (mutually exclusive).
 */

import React, { useState } from 'react';
import { Wrench, Microscope, Globe, Settings, Circle, CircleDot } from 'lucide-react';
import { Button } from '@/lib/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/lib/components/ui/dropdown-menu';
import type { AgentCardInfo } from '@/lib/types';
import type { DeepResearchSettings } from './deepResearchSettings';

interface ToolsSelectorProps {
  deepResearchEnabled: boolean;
  webSearchEnabled: boolean;
  onDeepResearchToggle: (enabled: boolean) => void;
  onWebSearchToggle: (enabled: boolean) => void;
  disabled?: boolean;
  agents: AgentCardInfo[];
  deepResearchSettings?: DeepResearchSettings;
  onDeepResearchSettingsClick?: () => void;
}

export const ToolsSelector: React.FC<ToolsSelectorProps> = ({
  deepResearchEnabled,
  webSearchEnabled,
  onDeepResearchToggle,
  onWebSearchToggle,
  disabled,
  agents,
  onDeepResearchSettingsClick
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
          <DropdownMenuItem
            onSelect={(e) => {
              e.preventDefault();
              handleWebSearchSelect();
            }}
            className="flex items-center justify-between cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              <span>Web Search</span>
            </div>
            {webSearchEnabled ? (
              <CircleDot className="h-4 w-4" />
            ) : (
              <Circle className="h-4 w-4" />
            )}
          </DropdownMenuItem>
        )}
        
        {/* Deep Research Option */}
        {hasDeepResearch && (
          <>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                handleDeepResearchSelect();
              }}
              className="flex items-center justify-between cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <Microscope className="h-4 w-4" />
                <span>Deep Research</span>
              </div>
              {deepResearchEnabled ? (
                <CircleDot className="h-4 w-4" />
              ) : (
                <Circle className="h-4 w-4" />
              )}
            </DropdownMenuItem>
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