/**
 * Deep Research Settings Types and Constants
 * Web-only version - supports only web search
 */

export interface DeepResearchSettings {
  maxRuntimeSeconds: number;  // 120, 300, 600 (2, 5, 10 minutes)
  maxIterations: number;      // 1-10
  sources: Array<'web'>;  // Web-only: only web search
}

export const DEFAULT_DEEP_RESEARCH_SETTINGS: DeepResearchSettings = {
  maxRuntimeSeconds: 300,  // 5 minutes
  maxIterations: 10,  // duration will be the primary constraint
  sources: ['web']  // Web-only
};