/**
 * Schedule Builder Component
 * Calendar-style schedule builder
 */

import { useState, useEffect } from "react";
import { CheckCircle2 } from "lucide-react";
import { MessageBanner } from "@/lib/components/common/MessageBanner";

// Schedule builder types
type FrequencyType = "daily" | "weekly" | "monthly" | "hourly" | "custom";

interface ScheduleConfig {
  frequency: FrequencyType;
  time: string; // HH:MM format
  ampm: "AM" | "PM";
  weekDays: number[]; // 0-6 (Sunday-Saturday)
  monthDay: number; // 1-31
  hourInterval: number; // 1, 2, 3, 6, 12, 24
}

// Convert schedule config to cron expression
function scheduleToCron(config: ScheduleConfig): string {
  const [hours24, minutes] = config.time.split(":").map(Number);
  let hour = hours24;
  
  // Convert 12-hour to 24-hour format
  if (config.ampm === "PM" && hour !== 12) {
    hour += 12;
  } else if (config.ampm === "AM" && hour === 12) {
    hour = 0;
  }

  switch (config.frequency) {
    case "daily":
      return `${minutes} ${hour} * * *`;
    
    case "weekly": {
      if (config.weekDays.length === 0) return `${minutes} ${hour} * * *`;
      const days = config.weekDays.sort().join(",");
      return `${minutes} ${hour} * * ${days}`;
    }
    
    case "monthly":
      return `${minutes} ${hour} ${config.monthDay} * *`;
    
    case "hourly":
      if (config.hourInterval === 24) {
        return `${minutes} ${hour} * * *`;
      }
      return `${minutes} */${config.hourInterval} * * *`;
    
    default:
      return `${minutes} ${hour} * * *`;
  }
}

// Parse cron expression to schedule config (best effort)
function cronToSchedule(cron: string): ScheduleConfig | null {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return null;

  const [minute, hour, dayOfMonth, , dayOfWeek] = parts;
  
  // Parse time
  let hours24 = 9;
  let minutes = 0;
  
  if (hour !== "*" && !hour.includes("/")) {
    hours24 = parseInt(hour);
  }
  if (minute !== "*" && !minute.includes("/")) {
    minutes = parseInt(minute);
  }

  // Convert to 12-hour format
  let ampm: "AM" | "PM" = "AM";
  let hours12 = hours24;
  if (hours24 >= 12) {
    ampm = "PM";
    if (hours24 > 12) hours12 = hours24 - 12;
  } else if (hours24 === 0) {
    hours12 = 12;
  }

  const time = `${hours12.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  // Detect frequency
  if (hour.includes("/")) {
    // Hourly pattern
    const interval = parseInt(hour.split("/")[1]);
    return {
      frequency: "hourly",
      time,
      ampm,
      weekDays: [],
      monthDay: 1,
      hourInterval: interval,
    };
  } else if (dayOfWeek !== "*") {
    // Weekly pattern
    const days = dayOfWeek.split(",").map(d => parseInt(d));
    return {
      frequency: "weekly",
      time,
      ampm,
      weekDays: days,
      monthDay: 1,
      hourInterval: 1,
    };
  } else if (dayOfMonth !== "*") {
    // Monthly pattern
    return {
      frequency: "monthly",
      time,
      ampm,
      weekDays: [],
      monthDay: parseInt(dayOfMonth),
      hourInterval: 1,
    };
  } else {
    // Daily pattern
    return {
      frequency: "daily",
      time,
      ampm,
      weekDays: [],
      monthDay: 1,
      hourInterval: 1,
    };
  }
}

// Helper function to generate human-readable schedule description
function getScheduleDescription(config: ScheduleConfig): string {
  const timeStr = `${config.time} ${config.ampm}`;
  
  switch (config.frequency) {
    case "daily":
      return `Every day at ${timeStr}`;
    
    case "weekly": {
      if (config.weekDays.length === 0) return `Every day at ${timeStr}`;
      const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
      const days = config.weekDays.sort().map(d => dayNames[d]).join(", ");
      return `Every ${days} at ${timeStr}`;
    }
    
    case "monthly": {
      const suffix = config.monthDay === 1 ? "st" : config.monthDay === 2 ? "nd" : config.monthDay === 3 ? "rd" : "th";
      return `Monthly on the ${config.monthDay}${suffix} at ${timeStr}`;
    }
    
    case "hourly":
      if (config.hourInterval === 1) return "Every hour";
      if (config.hourInterval === 24) return `Every day at ${timeStr}`;
      return `Every ${config.hourInterval} hours`;
    
    default:
      return "Custom schedule";
  }
}

// Validate cron expression
function validateCron(cron: string): { valid: boolean; error?: string } {
  const trimmed = cron.trim();
  if (!trimmed) {
    return { valid: false, error: "Cron expression cannot be empty" };
  }

  const parts = trimmed.split(/\s+/);
  if (parts.length !== 5) {
    return { valid: false, error: "Cron expression must have exactly 5 fields (minute hour day month weekday)" };
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  // Validate minute (0-59)
  if (!isValidCronField(minute, 0, 59)) {
    return { valid: false, error: "Invalid minute field (must be 0-59 or * or */n)" };
  }

  // Validate hour (0-23)
  if (!isValidCronField(hour, 0, 23)) {
    return { valid: false, error: "Invalid hour field (must be 0-23 or * or */n)" };
  }

  // Validate day of month (1-31)
  if (!isValidCronField(dayOfMonth, 1, 31)) {
    return { valid: false, error: "Invalid day of month field (must be 1-31 or * or */n)" };
  }

  // Validate month (1-12)
  if (!isValidCronField(month, 1, 12)) {
    return { valid: false, error: "Invalid month field (must be 1-12 or * or */n)" };
  }

  // Validate day of week (0-6)
  if (!isValidCronField(dayOfWeek, 0, 6)) {
    return { valid: false, error: "Invalid day of week field (must be 0-6 or * or */n)" };
  }

  return { valid: true };
}

// Helper to validate individual cron field
function isValidCronField(field: string, min: number, max: number): boolean {
  // Wildcard
  if (field === "*") return true;

  // Step values (*/n)
  if (field.startsWith("*/")) {
    const step = parseInt(field.substring(2));
    return !isNaN(step) && step > 0 && step <= max;
  }

  // Range (n-m)
  if (field.includes("-")) {
    const [start, end] = field.split("-").map(Number);
    return !isNaN(start) && !isNaN(end) && start >= min && end <= max && start <= end;
  }

  // List (n,m,o)
  if (field.includes(",")) {
    const values = field.split(",").map(Number);
    return values.every(v => !isNaN(v) && v >= min && v <= max);
  }

  // Single value
  const value = parseInt(field);
  return !isNaN(value) && value >= min && value <= max;
}

export function ScheduleBuilder({
  value,
  onChange,
}: {
  value: string;
  onChange: (cron: string) => void;
}) {
  const [rawCron, setRawCron] = useState(value);
  const [cronValidation, setCronValidation] = useState<{ valid: boolean; error?: string }>({ valid: true });
  
  // Initialize schedule config from cron or use defaults
  const initialConfig: ScheduleConfig = cronToSchedule(value) || {
    frequency: "daily",
    time: "09:00",
    ampm: "AM",
    weekDays: [],
    monthDay: 1,
    hourInterval: 1,
  };
  
  const [config, setConfig] = useState<ScheduleConfig>(initialConfig);

  // Update cron when config changes (except in custom mode)
  useEffect(() => {
    if (config.frequency !== "custom") {
      const newCron = scheduleToCron(config);
      setRawCron(newCron);
      onChange(newCron);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);

  // Handle custom cron changes
  const handleRawCronChange = (newCron: string) => {
    setRawCron(newCron);
    const validation = validateCron(newCron);
    setCronValidation(validation);
    
    // Only propagate valid cron expressions
    if (validation.valid) {
      onChange(newCron);
    }
  };

  const updateConfig = (updates: Partial<ScheduleConfig>) => {
    setConfig({ ...config, ...updates });
  };

  // Show custom cron input when frequency is "custom"
  if (config.frequency === "custom") {
    return (
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Frequency</label>
          <select
            className="max-w-xs px-3 py-2 border rounded-md"
            value={config.frequency}
            onChange={(e) => updateConfig({ frequency: e.target.value as FrequencyType })}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
            <option value="hourly">Every X hours</option>
            <option value="custom">Custom (Cron Expression)</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium mb-2">Cron Expression</label>
          <div className="relative">
            <input
              type="text"
              className={`max-w-md w-full px-3 py-2 pr-10 border rounded-md font-mono text-sm ${
                !cronValidation.valid ? "border-destructive focus:ring-destructive" : ""
              }`}
              value={rawCron}
              onChange={(e) => handleRawCronChange(e.target.value)}
              placeholder="0 9 * * *"
            />
            {cronValidation.valid && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              </div>
            )}
          </div>
          {!cronValidation.valid && cronValidation.error ? (
            <MessageBanner variant="error" message={cronValidation.error} className="mt-2" />
          ) : (
            <p className="text-xs text-muted-foreground mt-1">
              Format: <span className="font-mono">minute hour day month weekday</span>
            </p>
          )}
        </div>

        {/* Syntax Guide */}
        <div className="bg-muted/30 rounded-lg p-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground">Common Examples:</p>
          <div className="space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-primary">0 9 * * *</span>
              <span className="text-muted-foreground">Every day at 9:00 AM</span>
            </div>
            <div className="flex justify-between">
              <span className="text-primary">0 */6 * * *</span>
              <span className="text-muted-foreground">Every 6 hours</span>
            </div>
            <div className="flex justify-between">
              <span className="text-primary">0 9 * * 1</span>
              <span className="text-muted-foreground">Every Monday at 9:00 AM</span>
            </div>
            <div className="flex justify-between">
              <span className="text-primary">0 0 1 * *</span>
              <span className="text-muted-foreground">First day of month at midnight</span>
            </div>
            <div className="flex justify-between">
              <span className="text-primary">*/15 * * * *</span>
              <span className="text-muted-foreground">Every 15 minutes</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Use <span className="font-mono">*</span> for "any", <span className="font-mono">,</span> for lists, <span className="font-mono">-</span> for ranges, <span className="font-mono">/</span> for intervals
          </p>
        </div>
      </div>
    );
  }

  // Simple mode (default)
  return (
    <div className="space-y-4">
      {/* Frequency Selector */}
      <div>
        <label className="block text-xs text-muted-foreground mb-2">Frequency</label>
        <select
          className="max-w-xs px-3 py-2 border rounded-md"
          value={config.frequency}
          onChange={(e) => updateConfig({ frequency: e.target.value as FrequencyType })}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="hourly">Every X hours</option>
          <option value="custom">Custom (Cron Expression)</option>
        </select>
      </div>

      {/* Hourly Interval */}
      {config.frequency === "hourly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Every</label>
          <select
            className="max-w-xs px-3 py-2 border rounded-md"
            value={config.hourInterval}
            onChange={(e) => updateConfig({ hourInterval: parseInt(e.target.value) })}
          >
            <option value="1">1 hour</option>
            <option value="2">2 hours</option>
            <option value="3">3 hours</option>
            <option value="6">6 hours</option>
            <option value="12">12 hours</option>
            <option value="24">24 hours</option>
          </select>
        </div>
      )}

      {/* Time Picker (for non-hourly) */}
      {config.frequency !== "hourly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Time</label>
          <div className="flex gap-2 items-center">
            <input
              type="text"
              className="w-20 px-2 py-1.5 border rounded-md text-center text-sm"
              value={config.time}
              onChange={(e) => {
                const value = e.target.value;
                // Validate format HH:MM where HH is 01-12
                if (value.match(/^(0[1-9]|1[0-2]):[0-5][0-9]$/) || value.length < 5) {
                  updateConfig({ time: value });
                }
              }}
              onBlur={(e) => {
                // Auto-format on blur
                const value = e.target.value;
                const match = value.match(/^(\d{1,2}):?(\d{0,2})$/);
                if (match) {
                  let hours = parseInt(match[1]);
                  const minutes = match[2] ? match[2].padStart(2, '0') : '00';
                  
                  // Clamp hours to 1-12
                  if (hours < 1) hours = 1;
                  if (hours > 12) hours = 12;
                  
                  updateConfig({ time: `${hours.toString().padStart(2, '0')}:${minutes}` });
                }
              }}
              placeholder="09:00"
              maxLength={5}
            />
            <select
              className="w-16 px-2 py-1.5 border rounded-md text-sm"
              value={config.ampm}
              onChange={(e) => updateConfig({ ampm: e.target.value as "AM" | "PM" })}
            >
              <option value="AM">AM</option>
              <option value="PM">PM</option>
            </select>
          </div>
        </div>
      )}

      {/* Weekly Day Selector */}
      {config.frequency === "weekly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Days of Week</label>
          <div className="flex gap-2 flex-wrap">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  const newDays = config.weekDays.includes(idx)
                    ? config.weekDays.filter((d) => d !== idx)
                    : [...config.weekDays, idx];
                  updateConfig({ weekDays: newDays });
                }}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  config.weekDays.includes(idx)
                    ? "bg-primary text-primary-foreground"
                    : "bg-accent hover:bg-accent/80"
                }`}
              >
                {day}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Monthly Day Selector */}
      {config.frequency === "monthly" && (
        <div>
          <label className="block text-xs text-muted-foreground mb-2">Day of Month</label>
          <select
            className="max-w-xs px-3 py-2 border rounded-md"
            value={config.monthDay}
            onChange={(e) => updateConfig({ monthDay: parseInt(e.target.value) })}
          >
            {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
              <option key={day} value={day}>
                {day}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Preview */}
      {(
        <div className="bg-accent/30 rounded-lg p-3 text-sm">
          <p className="text-xs text-muted-foreground mb-1">Preview:</p>
          <p className="font-medium">{getScheduleDescription(config)}</p>
        </div>
      )}
    </div>
  );
}