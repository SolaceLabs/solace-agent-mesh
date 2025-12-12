# @Mentions Feature

## Overview

The @mentions feature allows you to reference colleagues in chat messages. When you mention someone, their information is included in the message sent to the agent, making it easier to ask questions about specific people or request actions involving them.

## Usage

### Creating a Mention

1. **Start typing**: Type `@` in the chat input field
2. **Continue typing**: Add at least 2 characters of the person's name
3. **Select from list**: A popup will appear with matching people
4. **Choose a person**: Use your mouse to click or keyboard to navigate and select

### Example

```
Type: "@joh"
Popup shows: John Doe, John Smith
Select: John Doe
Result: "@John Doe" appears in your message
```

### Complete Message Example

```
Hey @John Doe, can you review the proposal I sent you?
```

When submitted, the agent receives:
```
Hey John Doe <id:john.doe@example.com>, can you review the proposal I sent you?
```

## Keyboard Shortcuts

### Navigation

- **Arrow Up/Down**: Navigate through the list of matching people
- **Enter** or **Tab**: Select the highlighted person
- **Escape**: Close the mention popup without selecting
- **Backspace** (on empty query): Close the mention popup and return to typing

### Tips

- You can navigate with the keyboard or mouse
- Hover over a person with your mouse to highlight them
- Press Enter or Tab to quickly select the highlighted person

## Features

### Smart Search

The search finds people by:
- **First name**: "@john" finds "John Doe"
- **Last name**: "@doe" finds "John Doe"
- **Full name**: "@john doe" finds "John Doe"
- **Email**: "@john.doe" finds "john.doe@example.com"
- **Partial matches**: "@jo" finds "John", "Joe", "Joseph"

### Multiple Mentions

You can mention multiple people in a single message:

```
@John Doe and @Jane Smith, please collaborate on this task.
```

Each mention will be properly formatted when sent to the agent.

### Mention Position

Mentions work anywhere in your message:
- **Start**: "@John Hello!"
- **Middle**: "Hello @John how are you?"
- **End**: "Hello @John"

## Backend Format

When you submit a message with mentions, they are automatically converted to a format the agent understands:

**What you type:**
```
@Edward Funnekotter
```

**What the agent receives:**
```
Edward Funnekotter <id:edward.funnekotter@solace.com>
```

This ensures the agent knows exactly who you're referring to, even if multiple people have similar names.

## Common Use Cases

### Asking About People

```
What projects is @John Doe currently working on?
```

### Requesting Actions

```
Please send a summary to @Jane Smith and @Bob Wilson.
```

### Team Questions

```
Who are @Alice Johnson's direct reports?
```

### Availability Queries

```
Is @Charlie Brown available next Tuesday?
```

## Tips and Best Practices

### 1. Use Full Names

While search is flexible, using full names ensures you select the right person:
- ✅ "@John Doe" - Clear and specific
- ⚠️ "@John" - Might match multiple people

### 2. Verify Selection

Check that the correct person appears in your message before sending:
- Look for the full name in the mention
- The popup shows both name and email to help you choose

### 3. Edit Carefully

If you edit a mention after inserting it:
- Partial edits break the mention formatting
- It's better to delete and recreate the mention

### 4. Multiple Mentions

When mentioning several people, add them one at a time:
```
@John Doe, @Jane Smith, and @Bob Wilson
```

## Troubleshooting

### Popup doesn't appear

**Solution**: Make sure you've typed at least 2 characters after the `@` symbol.

```
@j  ❌ Too short
@jo ✅ Popup appears
```

### Can't find a person

**Possible reasons:**
1. **Name spelling**: Double-check the spelling
2. **Not in directory**: The person may not be in the employee database
3. **Search query**: Try searching by last name or email instead

### Mention not formatted correctly

If the mention isn't converted properly when sent:
1. Make sure you selected the person from the popup (don't just type "@Name")
2. Don't manually edit the mention after inserting it
3. If you need to fix it, delete and recreate the mention

### Popup shows too many results

**Solution**: Type more characters to narrow down the search:
```
@jo        Shows: John, Joe, Joseph, Joanna
@john do   Shows: John Doe
```

## Privacy and Security

### What Information is Shared

When you mention someone:
- Their name and ID (email) are sent to the agent
- No sensitive information beyond what's in the employee directory
- The agent uses this to understand context and provide relevant responses

### Who Can Be Mentioned

You can mention anyone in your organization's employee directory that you have access to search.

## Related Features

- **Slash Commands** (`/`): Quick access to prompt templates
- **File Attachments**: Share files with your messages
- **Context Selection**: Reference specific text from chat history

## Feedback

If you encounter issues with the mentions feature or have suggestions for improvements, please contact your administrator or submit feedback through the application.

## Configuration

For administrators looking to configure the identity service that powers mentions, see:
- [Identity Service Configuration](../configuration/identity_service.md)
- [Employee Directory Setup](../configuration/employee_service.md)
