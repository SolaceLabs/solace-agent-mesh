/**
 * Deep Research Settings Panel Component (Web-Only Version)
 *
 * Provides UI controls for configuring deep research parameters:
 * - Duration (max runtime)
 * - Depth (max iterations)
 * - Sources (web, kb only)
 */

import React, { useEffect, useRef } from 'react';
import { Globe } from 'lucide-react';
import type { DeepResearchSettings } from './deepResearchSettings';

interface DeepResearchSettingsPanelProps {
  settings: DeepResearchSettings;
  onSettingsChange: (settings: Partial<DeepResearchSettings>) => void;
  isOpen: boolean;
  onToggle: () => void;
}

const DURATION_OPTIONS = [
  { label: 'Quick', value: 120 },
  { label: 'Standard', value: 300 },
  { label: 'Deep', value: 600 }
];


export const DeepResearchSettingsPanel: React.FC<DeepResearchSettingsPanelProps> = ({
  settings,
  onSettingsChange,
  isOpen,
  onToggle
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  
  
  // Close panel when clicking outside
  useEffect(() => {
    if (!isOpen) return;
    
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        onToggle();
      }
    };
    
    // Add small delay to prevent immediate close from the settings button click
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);
    
    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onToggle]);
  
  if (!isOpen) return null;
  
  return (
    <div
      ref={panelRef}
      className="w-80 bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg shadow-lg p-4 space-y-4"
    >
      <div>
        <h3 className="font-semibold text-sm">Research Settings</h3>
      </div>

          {/* Mode Selection */}
          <div>
            <label className="text-sm font-medium block mb-2">Mode</label>
            <div className="flex gap-2">
              {DURATION_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => onSettingsChange({ maxRuntimeSeconds: opt.value })}
                  className={`
                    flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-all
                    ${settings.maxRuntimeSeconds === opt.value
                      ? 'bg-blue-100 text-blue-700 border-2 border-blue-500 dark:bg-blue-900 dark:text-blue-200'
                      : 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'
                    }
                  `}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Source info - Web only for now */}
          <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 p-2 rounded">
            <div className="flex items-center gap-2">
              <Globe className="h-3 w-3" />
              <span>Searching web sources only</span>
            </div>
          </div>
        </div>
  );
};