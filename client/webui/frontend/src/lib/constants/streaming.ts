/**
 * Constants for streaming markdown rendering
 * These control the adaptive speed algorithm that smooths out text rendering
 */

// Initial state values
export const STREAMING_INITIAL_SPEED = 0.03; // Initial conservative speed (30 chars/sec)
export const STREAMING_INITIAL_AVG_INTERVAL = 500; // Estimate 500ms between chunks initially

// Moving average alpha values for inter-arrival time calculation
export const STREAMING_ALPHA_FAST = 0.05; // Alpha when dt < threshold (more smoothing)
export const STREAMING_ALPHA_SLOW = 0.2; // Alpha when dt >= threshold (faster adaptation)
export const STREAMING_ALPHA_THRESHOLD_MS = 200; // Threshold to decide which alpha to use

// Time delta clamps to avoid extreme spikes from jitter
export const STREAMING_DT_MIN_MS = 20; // Minimum allowed dt value
export const STREAMING_DT_MAX_MS = 5000; // Maximum allowed dt value

// Speed calculation factors
export const STREAMING_SAFETY_FACTOR = 1.5; // Buffer factor for interval calculation
export const STREAMING_MOMENTUM_INCREASE = 0.5; // Momentum when increasing speed
export const STREAMING_MOMENTUM_DECREASE = 0.8; // Momentum when decreasing speed

// Speed clamps
export const STREAMING_SPEED_MIN = 0.005; // Minimum possible speed value
export const STREAMING_SPEED_MAX = 3.0; // Maximum possible speed value
