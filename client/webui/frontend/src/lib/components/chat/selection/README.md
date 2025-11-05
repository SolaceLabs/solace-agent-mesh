# Text Selection Context Menu Feature

## Overview

This feature enables users to select text from AI responses in the chat interface and access a context menu with actions like "Ask follow-up question" to continue the conversation based on the selected content.

## Components

### 1. TextSelectionProvider

**Location:** `TextSelectionProvider.tsx`

**Purpose:** Manages global selection state using React Context API.

**State:**
- `selectedText`: The currently selected text
- `selectionRange`: Browser Range object for the selection
- `menuPosition`: {x, y} coordinates for menu placement
- `sourceMessageId`: ID of the message containing the selection
- `isMenuOpen`: Whether the context menu is visible

**Methods:**
- `setSelection()`: Updates selection state and opens menu
- `clearSelection()`: Clears selection and closes menu
- `handleFollowUpQuestion()`: Dispatches event for ChatInputArea

**Usage:**
```typescript
import { useTextSelection } from './selection';

const { selectedText, isMenuOpen, clearSelection } = useTextSelection();
```

### 2. SelectableMessageContent

**Location:** `SelectableMessageContent.tsx`

**Purpose:** Wraps AI message content to detect text selection.

**Features:**
- Listens for `mouseup` events
- Validates selection (minimum 3 characters)
- Calculates optimal menu position
- Only activates for AI messages (not user messages)
- Handles viewport boundary detection

**Props:**
```typescript
interface SelectableMessageContentProps {
  messageId: string;
  children: React.ReactNode;
  isAIMessage: boolean;
}
```

### 3. SelectionContextMenu

**Location:** `SelectionContextMenu.tsx`

**Purpose:** Displays context menu with actions for selected text.

**Actions:**
- 📄 **Summarize**: Automatically asks "Summarize this:" with the selected text
- 💡 **Explain**: Automatically asks "Explain this in detail:" with the selected text
- 📝 **Custom question...**: Opens an inline input field for custom queries
- 📋 **Copy to clipboard**: Copies text to clipboard

**Custom Question Mode:**
When "Custom question..." is selected, the menu transforms to show:
- Text input field for typing custom questions
- Send button to submit
- Escape key to go back to main menu
- Enter key to submit (Shift+Enter for new line)

**Features:**
- Positioned at cursor location
- Auto-closes on:
  - Click outside
  - Escape key press
  - Scroll events
  - New selection
- Smooth fade-in animation
- Proper z-index layering

### 4. Utility Functions

**Location:** `selectionUtils.ts`

**Functions:**
- `getSelectedText()`: Gets current browser selection as text
- `getSelectionRange()`: Gets current Range object
- `getSelectionBoundingRect()`: Gets selection bounds
- `calculateMenuPosition()`: Calculates menu position with viewport boundary handling
- `isValidSelection()`: Validates selection (min 3 chars, not whitespace)
- `clearBrowserSelection()`: Clears browser selection

## Integration

### ChatMessage Component

AI messages are wrapped with `SelectableMessageContent`:

```typescript
if (!message.isUser) {
  return (
    <SelectableMessageContent 
      messageId={message.metadata?.messageId || ''}
      isAIMessage={true}
    >
      {renderContent()}
    </SelectableMessageContent>
  );
}
```

### ChatInputArea Component

Handles follow-up questions via custom events with optional prompts:

```typescript
useEffect(() => {
  const handleFollowUp = (event: Event) => {
    const { text, prompt } = (event as CustomEvent).detail;
    setContextText(text);
    
    // Pre-fill input with prompt if provided
    if (prompt) {
      setInputValue(prompt + " ");
    }
    
    chatInputRef.current?.focus();
  };

  window.addEventListener('follow-up-question', handleFollowUp);
  return () => window.removeEventListener('follow-up-question', handleFollowUp);
}, []);
```

When submitting, context is prepended to the message:

```typescript
if (contextText) {
  fullMessage = `Context: "${contextText}"\n\n${fullMessage}`;
}
```

**Quick Actions:**
- **Summarize**: Pre-fills input with "Summarize this: "
- **Explain**: Pre-fills input with "Explain this in detail: "
- **Custom**: Shows inline input for custom questions

### App Component

Wraps application with provider and renders menu:

```typescript
<TextSelectionProvider>
  <AppContentInner />
  <SelectionContextMenu
    isOpen={isMenuOpen}
    position={menuPosition}
    selectedText={selectedText || ''}
    onClose={clearSelection}
    onFollowUpQuestion={handleFollowUpQuestion}
  />
</TextSelectionProvider>
```

## User Flow

1. **Selection**
   - User reads AI response
   - User clicks and drags to select text (minimum 3 characters)
   - Selection is highlighted by browser

2. **Menu Appearance**
   - Context menu appears near cursor
   - Menu shows 4 action options
   - Smooth fade-in animation

3. **Quick Actions**
   - **Summarize**: Clicks "Summarize" → Input pre-filled with "Summarize this: "
   - **Explain**: Clicks "Explain" → Input pre-filled with "Explain this in detail: "
   - Context badge shows selected text
   - User can edit or submit immediately

4. **Custom Question**
   - User clicks "Custom question..."
   - Menu transforms to show input field
   - User types custom question
   - User presses Enter or clicks Send
   - Chat input receives the custom question with context

4. **Message Sent**
   - Message includes: `Context: "selected text"\n\nUser's question`
   - AI receives full context for better responses
   - Context badge is cleared

## Features

### Text Selection
- ✅ Only works on AI responses (user messages excluded)
- ✅ Minimum 3 characters required
- ✅ Validates non-whitespace content
- ✅ Handles multi-line selections
- ✅ Works with markdown-rendered content

### Context Menu
- ✅ Positioned near cursor
- ✅ Stays within viewport boundaries
- ✅ Auto-closes on click outside
- ✅ Auto-closes on Escape key
- ✅ Auto-closes on scroll
- ✅ Smooth animations
- ✅ Transforms to show custom input mode

### Quick Actions
- ✅ **Summarize**: Pre-fills "Summarize this: "
- ✅ **Explain**: Pre-fills "Explain this in detail: "
- ✅ **Custom question**: Inline input for custom queries
- ✅ **Copy**: Copies text to clipboard

### Follow-up Questions
- ✅ Context badge in input area
- ✅ Removable context (X button)
- ✅ Context prepended to message
- ✅ Auto-focus on input
- ✅ Pre-filled prompts for quick actions
- ✅ Inline custom question input
- ✅ Clears after submission

## Styling

The feature uses existing UI components and follows the application's theme:
- `Button` component for menu actions
- `Badge` component for context display
- CSS animations from existing system
- Theme-aware colors and spacing

## Accessibility

- ✅ Keyboard navigation (Escape to close)
- ✅ Focus management
- ✅ ARIA labels on buttons
- ✅ Screen reader compatible

## Browser Compatibility

- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- Uses standard Selection API (widely supported)

## Performance

- React.memo used for SelectableMessageContent
- Event listeners properly cleaned up
- Minimal re-renders
- Efficient state management

## Future Enhancements

Potential additions:
- Additional quick actions (Simplify, Translate, Fix grammar)
- Highlight referenced text in original message
- Thread view for follow-up questions
- Keyboard shortcuts (Cmd/Ctrl + K for custom question)
- Mobile touch selection support
- Selection history
- Save frequently used custom questions

## Testing

Key scenarios to test:
- Select text in AI messages ✓
- Verify user messages are not selectable ✓
- Test menu positioning at screen edges
- Test with long selections
- Test with markdown content
- Test with code blocks
- Test menu auto-close behaviors
- Test keyboard navigation
- Test context badge display and removal
- Test message submission with context

## Troubleshooting

**Menu doesn't appear:**
- Check if selection is at least 3 characters
- Verify selection is in an AI message (not user message)
- Check browser console for errors

**Menu appears in wrong position:**
- Check viewport boundaries
- Verify calculateMenuPosition logic
- Test with different screen sizes

**Context not included in message:**
- Verify follow-up-question event is dispatched
- Check ChatInputArea event listener
- Verify context text state management