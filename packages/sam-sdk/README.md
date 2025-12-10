# SAM SDK

TypeScript SDK for building iframe-based applications on the SAM platform.

## Installation

```bash
npm install @sam/sdk
```

## Quick Start

```typescript
import { SAM } from '@sam/sdk';

// Wait for SDK to be ready
await SAM.ready();

// Call other SAM agents
const result = await SAM.agents.call('data-analyzer', {
  prompt: 'Analyze this sales data',
  context: { dataset: salesData }
});

// Use app-scoped storage
await SAM.storage.set('preferences', {
  theme: 'dark',
  layout: 'grid'
});

const prefs = await SAM.storage.get('preferences');

// Handle artifacts
const artifactId = await SAM.artifacts.upload(file);
const blob = await SAM.artifacts.download(artifactId);

// Get current theme
const theme = SAM.ui.getTheme(); // 'light' | 'dark'

// Listen for theme changes
const unsubscribe = SAM.ui.onThemeChange((theme) => {
  console.log('Theme changed to:', theme);
});
```

## API Reference

### SAM.ready()

Wait for the SDK to establish communication with the parent SAM frame.

```typescript
await SAM.ready();
```

### SAM.agents

Call other agents in the SAM ecosystem.

```typescript
interface AgentCallOptions {
  prompt: string;
  context?: Record<string, any>;
  stream?: boolean;
}

interface AgentCallResult {
  response: string;
  artifacts?: string[];
  metadata?: Record<string, any>;
}

const result = await SAM.agents.call('agent-name', {
  prompt: 'Your prompt here',
  context: { key: 'value' }
});
```

### SAM.storage

Persistent key-value storage scoped to your app and the current user.

```typescript
// Set value (any JSON-serializable data)
await SAM.storage.set('key', value);

// Get value
const value = await SAM.storage.get<YourType>('key');

// Delete value
await SAM.storage.delete('key');

// List keys (with optional prefix)
const keys = await SAM.storage.list('prefix.');

// Clear all storage
await SAM.storage.clear();
```

### SAM.artifacts

Upload and download files/artifacts.

```typescript
// Upload file
const artifactId = await SAM.artifacts.upload(file);

// Download file
const blob = await SAM.artifacts.download(artifactId);
```

### SAM.ui

Access UI state and react to changes.

```typescript
// Get current theme
const theme = SAM.ui.getTheme(); // 'light' | 'dark'

// Listen for theme changes
const unsubscribe = SAM.ui.onThemeChange((theme) => {
  console.log('Theme changed to:', theme);
  // Update your app's styling
});

// Stop listening (cleanup)
unsubscribe();
```

## React Integration

```tsx
import { SAM } from '@sam/sdk';
import { useEffect, useState } from 'react';

function App() {
  const [theme, setTheme] = useState(SAM.ui.getTheme());
  const [data, setData] = useState(null);

  useEffect(() => {
    // Initialize SDK
    SAM.ready().then(async () => {
      // Load data from storage
      const saved = await SAM.storage.get('myData');
      setData(saved);
    });

    // Listen for theme changes
    const unsubscribe = SAM.ui.onThemeChange(setTheme);
    return unsubscribe;
  }, []);

  const handleSave = async () => {
    await SAM.storage.set('myData', data);
  };

  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      {/* Your app UI */}
    </div>
  );
}
```

## TypeScript Support

The SDK is written in TypeScript and includes full type definitions.

```typescript
import type { AgentCallResult, Theme } from '@sam/sdk';
```

## Examples

### Dashboard App

```typescript
import { SAM } from '@sam/sdk';

// Fetch data from SAM agent
const analyzeData = async () => {
  const result = await SAM.agents.call('data-analyzer', {
    prompt: 'Summarize sales trends for Q4',
    context: { year: 2024, quarter: 4 }
  });

  return result.response;
};

// Cache results in storage
const getCachedResults = async () => {
  const cached = await SAM.storage.get('q4-results');
  if (cached) return cached;

  const fresh = await analyzeData();
  await SAM.storage.set('q4-results', fresh);
  return fresh;
};
```

### Form Builder

```typescript
import { SAM } from '@sam/sdk';

// Save draft
const saveDraft = async (formData: any) => {
  await SAM.storage.set('draft', formData);
};

// Submit to agent for processing
const submitForm = async (formData: any) => {
  const result = await SAM.agents.call('form-processor', {
    prompt: 'Process this form submission',
    context: formData
  });

  // Clear draft after successful submission
  await SAM.storage.delete('draft');

  return result;
};
```

### Document Viewer

```typescript
import { SAM } from '@sam/sdk';

// Upload document
const uploadDocument = async (file: File) => {
  const artifactId = await SAM.artifacts.upload(file);

  // Analyze with agent
  const analysis = await SAM.agents.call('document-analyzer', {
    prompt: 'Extract key information from this document',
    context: { artifactId }
  });

  return analysis;
};
```

## Development

```bash
# Install dependencies
npm install

# Build SDK
npm run build

# Watch mode (for development)
npm run dev

# Type checking
npm run typecheck

# Linting
npm run lint
```

## License

MIT
