# SAM App Template

This workspace contains a React application template for building SAM platform apps.

## Environment

- **React 19**: Latest React with improved performance and concurrent features
- **TypeScript 5.8**: Type-safe development with latest TypeScript features
- **Vite 6**: Ultra-fast build tooling with instant HMR
- **Tailwind CSS 3.4**: Utility-first CSS framework for rapid UI development
- **SAM SDK**: TypeScript SDK for SAM platform integration
- **ESLint**: Code quality and consistency

## Project Structure

```
/workspace
├── src/
│   ├── main.tsx          # Application entry point
│   ├── App.tsx           # Root component (includes SAM SDK examples)
│   └── index.css         # Global styles with Tailwind imports
├── public/               # Static assets
├── index.html            # HTML entry point
├── vite.config.ts        # Vite configuration
├── tailwind.config.ts    # Tailwind configuration
├── tsconfig.json         # TypeScript configuration
└── package.json          # Dependencies and scripts
```

## Development Workflow

The App Agent will help you build this application through conversation:

1. **Requirements Gathering**: The agent will ask clarifying questions to understand your needs
2. **Incremental Development**: Features are built one at a time with your feedback
3. **Live Preview**: Changes appear instantly in the preview pane via Vite HMR
4. **Build Validation**: When ready to deploy, the build process ensures everything compiles correctly

## SAM SDK Documentation

### Overview

The SAM SDK (`@sam/sdk`) is a **production-ready TypeScript library** that enables your app to integrate with the SAM platform via `postMessage` communication with the parent frame.

**IMPORTANT**: This is NOT a mock or test SDK. All API calls communicate with the real SAM platform:
- `SAM.agents.call()` → Calls actual SAM agents in the platform
- `SAM.storage` → Reads/writes real persistent storage
- `SAM.artifacts` → Uploads/downloads real files
- `SAM.ui` → Gets real theme state from parent

The SDK provides APIs for:

- **Agent Calling**: Invoke other SAM agents from your app
- **Storage**: Persistent, app-scoped key-value data storage
- **Artifacts**: File upload/download
- **UI Integration**: Theme detection and dark mode support

### Installation

The SAM SDK is already installed in this template. Import it in your components:

```typescript
import { SAM } from '@sam/sdk'
import type { Theme } from '@sam/sdk'
```

### Initialization

**IMPORTANT**: Always call `SAM.ready()` before using any SDK features.

```typescript
import { useEffect } from 'react'
import { SAM } from '@sam/sdk'

function App() {
  useEffect(() => {
    const init = async () => {
      // Wait for SDK to establish connection with parent frame
      await SAM.ready()

      // Now safe to use all SDK features
      const theme = SAM.ui.getTheme()
      // ...
    }

    init()
  }, [])
}
```

### API Reference

#### 1. SAM.ready()

Wait for the SDK to establish communication with the parent SAM frame.

```typescript
await SAM.ready()
```

**Usage Pattern:**
```typescript
useEffect(() => {
  SAM.ready().then(() => {
    console.log('SDK is ready!')
    // Initialize your app
  })
}, [])
```

---

#### 2. SAM.agents - Call Other Agents

Call other agents in the SAM ecosystem from your app.

**Method:**
```typescript
SAM.agents.call(agentName: string, options: AgentCallOptions): Promise<AgentCallResult>
```

**Types:**
```typescript
interface AgentCallOptions {
  prompt: string                    // Required: The prompt/instruction for the agent
  context?: Record<string, any>     // Optional: Additional context data
  stream?: boolean                  // Optional: Enable streaming response
  onText?: (text: string) => void   // Optional: Callback for streaming text chunks
  onStatus?: (status: string) => void // Optional: Callback for status updates
  onArtifact?: (artifact: any) => void // Optional: Callback when an artifact is created
}

interface AgentCallResult {
  response: string                  // The agent's response
  artifacts?: string[]              // Array of artifact IDs (if any)
  metadata?: Record<string, any>    // Additional response metadata
}
```

**Example: Call a data analysis agent**
```typescript
const analyzeData = async () => {
  const result = await SAM.agents.call('data-analyzer', {
    prompt: 'Analyze sales trends for Q4 2024',
    context: {
      year: 2024,
      quarter: 4,
      metrics: ['revenue', 'growth']
    },
    onText: (text) => console.log('Stream:', text),
    onStatus: (status) => console.log('Status:', status)
  })

  console.log('Analysis:', result.response)

  if (result.artifacts) {
    console.log('Generated artifacts:', result.artifacts)
  }
}
```

**Example: Interactive agent call with user input**
```typescript
function AgentCallDemo() {
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCall = async () => {
    setLoading(true)
    try {
      const result = await SAM.agents.call('your-agent-name', {
        prompt,
        context: { source: 'my-app' }
      })
      setResponse(result.response)
    } catch (error) {
      console.error('Agent call failed:', error)
      setResponse('Error: ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <input value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <button onClick={handleCall} disabled={loading}>
        {loading ? 'Calling...' : 'Call Agent'}
      </button>
      {response && <p>{response}</p>}
    </div>
  )
}
```

---

#### 3. SAM.storage - Persistent Data Storage

App-scoped, user-specific key-value storage that persists across sessions.

**Methods:**

**Get a value:**
```typescript
SAM.storage.get<T>(key: string): Promise<T | null>
```

**Set a value:**
```typescript
SAM.storage.set<T>(key: string, value: T): Promise<void>
```

**Delete a value:**
```typescript
SAM.storage.delete(key: string): Promise<void>
```

**List keys:**
```typescript
SAM.storage.list(prefix?: string): Promise<string[]>
```

**Clear all storage:**
```typescript
SAM.storage.clear(): Promise<void>
```

**Example: Save user preferences**
```typescript
interface UserPreferences {
  theme: 'light' | 'dark'
  layout: 'grid' | 'list'
  notifications: boolean
}

const savePreferences = async (prefs: UserPreferences) => {
  await SAM.storage.set('user-preferences', prefs)
}

const loadPreferences = async (): Promise<UserPreferences | null> => {
  return await SAM.storage.get<UserPreferences>('user-preferences')
}
```

**Example: Form draft auto-save**
```typescript
function DraftForm() {
  const [formData, setFormData] = useState({})

  // Auto-save draft every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      if (Object.keys(formData).length > 0) {
        await SAM.storage.set('form-draft', formData)
        console.log('Draft saved')
      }
    }, 30000)

    return () => clearInterval(interval)
  }, [formData])

  // Load draft on mount
  useEffect(() => {
    const loadDraft = async () => {
      const draft = await SAM.storage.get('form-draft')
      if (draft) {
        setFormData(draft)
      }
    }
    loadDraft()
  }, [])

  const handleSubmit = async () => {
    // Submit form
    // ...
    // Clear draft after successful submission
    await SAM.storage.delete('form-draft')
  }
}
```

**Example: List all saved items**
```typescript
const listSavedItems = async () => {
  // Get all keys starting with 'item-'
  const keys = await SAM.storage.list('item-')

  // Load all items
  const items = await Promise.all(
    keys.map(key => SAM.storage.get(key))
  )

  return items.filter(item => item !== null)
}
```

---

#### 4. SAM.artifacts - File Management

Upload and download files/artifacts.

**Upload a file:**
```typescript
SAM.artifacts.upload(file: File): Promise<string>
```
Returns the artifact ID.

**Download a file:**
```typescript
SAM.artifacts.download(artifactId: string): Promise<Blob>
```
Returns the file as a Blob.

**Example: Upload user file**
```typescript
function FileUploader() {
  const [uploading, setUploading] = useState(false)
  const [artifactId, setArtifactId] = useState<string | null>(null)

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const id = await SAM.artifacts.upload(file)
      setArtifactId(id)
      console.log('Uploaded successfully:', id)

      // Now you can pass this artifact ID to an agent
      await SAM.agents.call('document-analyzer', {
        prompt: 'Analyze this document',
        context: { artifactId: id }
      })
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <input
        type="file"
        onChange={handleUpload}
        disabled={uploading}
      />
      {uploading && <p>Uploading...</p>}
      {artifactId && <p>Artifact ID: {artifactId}</p>}
    </div>
  )
}
```

**Example: Download and display file**
```typescript
const downloadFile = async (artifactId: string) => {
  const blob = await SAM.artifacts.download(artifactId)

  // Create download link
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'downloaded-file'
  a.click()
  URL.revokeObjectURL(url)
}
```

---

#### 5. SAM.ui - Theme and UI State

Access UI state and react to changes.

**Get current theme:**
```typescript
SAM.ui.getTheme(): Theme  // 'light' | 'dark'
```

**Listen for theme changes:**
```typescript
SAM.ui.onThemeChange(callback: (theme: Theme) => void): () => void
```
Returns an unsubscribe function.

**Example: React to theme changes**
```typescript
import { useEffect, useState } from 'react'
import { SAM } from '@sam/sdk'
import type { Theme } from '@sam/sdk'

function App() {
  const [theme, setTheme] = useState<Theme>('light')

  useEffect(() => {
    SAM.ready().then(() => {
      // Get initial theme
      setTheme(SAM.ui.getTheme())

      // Listen for changes
      const unsubscribe = SAM.ui.onThemeChange((newTheme) => {
        setTheme(newTheme)
        console.log('Theme changed to:', newTheme)
      })

      // Cleanup
      return unsubscribe
    })
  }, [])

  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      {/* Your app with dark mode support */}
    </div>
  )
}
```

**Example: Dynamic Tailwind classes based on theme**
```typescript
function ThemedCard() {
  const [theme, setTheme] = useState<Theme>('light')

  useEffect(() => {
    SAM.ready().then(() => {
      setTheme(SAM.ui.getTheme())
      return SAM.ui.onThemeChange(setTheme)
    })
  }, [])

  const isDark = theme === 'dark'

  return (
    <div className={`
      ${isDark ? 'bg-gray-800 text-white' : 'bg-white text-gray-900'}
      p-4 rounded-lg shadow
    `}>
      <h2>Current theme: {theme}</h2>
    </div>
  )
}
```

---

### Error Handling

Always wrap SDK calls in try-catch blocks:

```typescript
try {
  const result = await SAM.agents.call('agent-name', { prompt: 'test' })
  console.log(result)
} catch (error) {
  console.error('Failed to call agent:', error)
  // Show error to user
}
```

### Common Patterns

#### Loading States

```typescript
function MyComponent() {
  const [sdkReady, setSdkReady] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    SAM.ready().then(() => setSdkReady(true))
  }, [])

  if (!sdkReady) {
    return <div>Connecting to SAM...</div>
  }

  const handleAction = async () => {
    setLoading(true)
    try {
      await SAM.storage.set('key', 'value')
    } finally {
      setLoading(false)
    }
  }

  return (
    <button onClick={handleAction} disabled={loading}>
      {loading ? 'Saving...' : 'Save'}
    </button>
  )
}
```

#### Caching Agent Responses

```typescript
const getCachedAnalysis = async (prompt: string) => {
  // Check cache first
  const cached = await SAM.storage.get(`cache-${prompt}`)
  if (cached) return cached

  // Call agent if not cached
  const result = await SAM.agents.call('analyzer', { prompt })

  // Save to cache
  await SAM.storage.set(`cache-${prompt}`, result.response)

  return result.response
}
```

---

## Styling Guidelines

**Always use Tailwind CSS for styling.** The template is pre-configured with Tailwind utilities.

### Responsive Design
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
```

### Dark Mode Support
```tsx
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
```

### Common Patterns
```tsx
// Buttons
<button className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg">

// Cards
<div className="bg-white rounded-lg shadow-xl p-6">

// Inputs
<input className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
```

---

## Code Quality Standards

1. **TypeScript**: All files should use TypeScript (.tsx, .ts)
2. **Type Safety**: Define interfaces for props and data structures
3. **Component Structure**: Use functional components with hooks
4. **Error Handling**: Always handle errors gracefully with try/catch
5. **Responsive Design**: Ensure apps work on mobile and desktop
6. **Accessibility**: Use semantic HTML and ARIA labels where appropriate

---

## Development Workflow

**Testing Your App:**

The App Agent automatically builds your app after making changes. To see updates:
1. Wait for the agent to finish making changes
2. Click the "Refresh" button in the preview pane
3. Your updated app will load instantly

**No need to run commands manually!** The build happens automatically when the agent makes changes.

## Available Scripts

These scripts are available if needed, but in normal development the App Agent handles building:

```bash
npm run build    # Build for production (runs automatically via App Agent)
npm run lint     # Run ESLint to check code quality
npm run preview  # Preview production build locally (optional)
```

---

## Building Your App

When you're ready to describe your app, provide:

1. **Purpose**: What problem does this app solve?
2. **Features**: What functionality do you need?
3. **Data Sources**: Will you call other SAM agents? What data do you need?
4. **UI/UX**: Any specific design requirements or preferences?

The App Agent will guide you through the development process, building your app incrementally based on your feedback.

---

## Example App Ideas

### Dashboard App
```typescript
// Fetch data from SAM agent and visualize
const data = await SAM.agents.call('data-analyzer', {
  prompt: 'Get Q4 sales summary',
  context: { year: 2024 }
})

// Cache in storage
await SAM.storage.set('q4-data', data.response)
```

### Form Builder
```typescript
// Auto-save drafts
useEffect(() => {
  const interval = setInterval(async () => {
    await SAM.storage.set('draft', formData)
  }, 30000)
  return () => clearInterval(interval)
}, [formData])

// Submit to agent
const handleSubmit = async () => {
  const result = await SAM.agents.call('form-processor', {
    prompt: 'Process form',
    context: formData
  })
}
```

### Document Viewer
```typescript
// Upload document
const artifactId = await SAM.artifacts.upload(file)

// Analyze with agent
const analysis = await SAM.agents.call('document-analyzer', {
  prompt: 'Extract key information',
  context: { artifactId }
})
```

---

Ready to start building? Describe your app requirements to the App Agent!
