# Project Sharing - Typeahead Dropdown Enhancement

## Feature Overview

This is a POC enhancement to the ShareDialog that adds a typeahead dropdown for user search as an alternative to manual email entry. Both methods (email input and typeahead) will coexist in the UI via a toggle, allowing demonstration of both approaches.

**Context**: This builds on the base project sharing feature. The ShareDialog component will be enhanced to support two modes for adding users.

## User Requirements

### Primary Flow (Typeahead Mode)

1. Owner opens ShareDialog
2. Toggles to "Search Users" mode
3. Types in a search box (e.g., "john")
4. Dropdown shows matching users as they type (debounced)
5. Can use arrow keys to navigate results
6. Selects user from dropdown
7. Selected user is added to "pending list" (default role: Viewer)
8. Can add multiple users to pending list
9. Can remove users from pending list before submitting
10. Clicks "Share" to submit all pending users sequentially
11. Progress/success feedback shown

### Alternative Flow (Email Mode - Existing)

1. Owner opens ShareDialog
2. Uses email input mode (current implementation)
3. Types email manually
4. Selects role
5. Invites one user at a time

### User Preferences (from clarification):

- **Toggle state**: Resets to email mode each time dialog opens (not persistent)
- **No results**: Show "No users found" message in dropdown
- **User display**: Name + Email in pending list
- **Submit**: Simple sequential (no progress bar needed)

## Backend API Contract

### New API: People Search

**Endpoint**: `GET /api/v1/people/search`

**Query Parameters**:

- `q` (string, required): Search query (name or email fragment)
- `limit` (number, optional): Maximum results to return (default: 10)

**Request Example**:

```bash
curl "http://127.0.0.1:8000/api/v1/people/search?q=john&limit=10" \
  -H "Authorization: Bearer john_token"
```

**Response**:

```json
{
    "data": [
        {
            "id": "john@test.com",
            "name": "John Admin",
            "email": "john@test.com",
            "title": null
        },
        {
            "id": "johnny-456",
            "name": "Johnny Editor",
            "email": "johnny@example.com",
            "title": "Software Engineer"
        }
    ]
}
```

**Field Details**:

- `id` (string): User's unique identifier (may be email or UUID)
- `name` (string): User's display name
- `email` (string): User's email address
- `title` (string | null): User's job title (may be null)

**Notes**:

- Requires authentication (Bearer token)
- Returns empty array `{"data": []}` if no matches
- Backend handles fuzzy matching on name and email fields

### Existing API: Share Project

**Endpoint**: `POST /api/v1/projects/{projectId}/share`

**Important Limitation**: Can only handle **ONE user at a time**. For multiple users, call this endpoint sequentially.

**Request Example**:

```bash
curl -X POST "http://localhost:8000/api/v1/projects/$PID/share" \
  -H "Authorization: Bearer $TOKEN" \
  -F "user_email=sarah@test.com" \
  -F "role=editor"
```

**Request Body** (Form Data):

- `user_email` (string): Email address from selected user
- `role` (string): For typeahead mode, always "viewer"

## Frontend Requirements

### Type Extensions

Add to `src/lib/types/projects.ts`:

```typescript
// People search API types
export interface PersonSearchResult {
    id: string;
    name: string;
    email: string;
    title: string | null;
}

export interface PeopleSearchResponse {
    data: PersonSearchResult[];
}

// Pending user (before submission)
export interface PendingCollaborator {
    id: string;
    name: string;
    email: string;
    role: "viewer"; // Always viewer for this POC
}
```

### New API Service

Create `src/lib/api/projects/people.ts`:

```typescript
import { ApiClient } from "@/lib/api/client";
import type { PeopleSearchResponse } from "@/lib/types/projects";

export const PeopleService = {
    /**
     * Search for users by name or email
     * @param query Search string (name or email fragment)
     * @param limit Maximum number of results (default: 10)
     */
    searchPeople: async (query: string, limit: number = 10): Promise<PeopleSearchResponse> => {
        return ApiClient.get(`/api/v1/people/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    },
};
```

### Component Updates: ShareDialog.tsx

**New State Variables**:

```typescript
// Mode toggle
const [useTypeahead, setUseTypeahead] = useState(false); // Default to email input

// Typeahead search state
const [searchQuery, setSearchQuery] = useState("");
const [searchResults, setSearchResults] = useState<PersonSearchResult[]>([]);
const [isSearching, setIsSearching] = useState(false);
const [selectedIndex, setSelectedIndex] = useState(-1); // For keyboard nav

// Pending users (before submission)
const [pendingUsers, setPendingUsers] = useState<PendingCollaborator[]>([]);
const [isSubmitting, setIsSubmitting] = useState(false);
```

**New Features to Implement**:

#### 1. Mode Toggle Switch

Located at top of "Add User" section:

- Use Switch component (Radix UI @radix-ui/react-switch or Shadcn)
- Label changes based on state: "Search Users" when checked, "Manual Email" when unchecked
- Resets to false (email mode) when dialog opens
- onChange clears any search state

```tsx
<div className="mb-4 flex items-center space-x-2">
    <Switch
        id="search-mode"
        checked={useTypeahead}
        onCheckedChange={checked => {
            setUseTypeahead(checked);
            setSearchQuery("");
            setSearchResults([]);
            setPendingUsers([]);
        }}
    />
    <Label htmlFor="search-mode">{useTypeahead ? "Search Users" : "Manual Email Entry"}</Label>
</div>
```

#### 2. Typeahead Search Input & Dropdown

**Search Input**:

- Text input with search icon (magnifying glass)
- Placeholder: "Search by name or email..."
- `value={searchQuery}` binds to state
- `onChange` updates search query (triggers debounced search)
- `onKeyDown` handles keyboard navigation
- Shows loading spinner when `isSearching`

**Debounced Search Logic**:

```typescript
const debouncedQuery = useDebounce(searchQuery, 300); // 300ms delay

useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
        setSearchResults([]);
        return;
    }

    const search = async () => {
        setIsSearching(true);
        try {
            const response = await PeopleService.searchPeople(debouncedQuery, 10);
            setSearchResults(response.data);
            setSelectedIndex(-1); // Reset selection
        } catch (error) {
            addNotification({ type: "error", message: "Failed to search users" });
            setSearchResults([]);
        } finally {
            setIsSearching(false);
        }
    };

    search();
}, [debouncedQuery]);
```

**Results Dropdown** (Popover):

- Positioned below search input
- Only visible when `searchResults.length > 0` or showing "No users found"
- Each result item displays:
    ```
    [Name]
    [Email] " [Title]  (title is optional, omit if null)
    ```
- Highlight selected item with background color
- Click to select user
- Shows "No users found" when empty and search query exists

#### 3. Keyboard Navigation

```typescript
const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!searchResults.length) return;

    switch (e.key) {
        case "ArrowDown":
            e.preventDefault();
            setSelectedIndex(prev => (prev < searchResults.length - 1 ? prev + 1 : prev));
            break;

        case "ArrowUp":
            e.preventDefault();
            setSelectedIndex(prev => (prev > 0 ? prev - 1 : -1));
            break;

        case "Enter":
            e.preventDefault();
            if (selectedIndex >= 0) {
                handleSelectUser(searchResults[selectedIndex]);
            }
            break;

        case "Escape":
            e.preventDefault();
            setSearchResults([]);
            setSearchQuery("");
            setSelectedIndex(-1);
            break;
    }
};
```

#### 4. Pending Users List

**Location**: Between search input and current collaborators list

**Display**:

```tsx
{
    pendingUsers.length > 0 && (
        <div className="pending-users-section">
            <h4 className="text-sm font-medium">Pending Invitations ({pendingUsers.length})</h4>
            <div className="space-y-2">
                {pendingUsers.map(user => (
                    <div key={user.id} className="flex items-center justify-between rounded border p-2">
                        <div>
                            <div className="font-medium">{user.name}</div>
                            <div className="text-muted-foreground text-sm">{user.email}</div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge variant="secondary">Viewer</Badge>
                            <Button variant="ghost" size="sm" onClick={() => removeFromPending(user.id)}>
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
```

**Add to Pending Logic**:

```typescript
const handleSelectUser = (user: PersonSearchResult) => {
    // Check if already in pending list
    if (pendingUsers.some(p => p.id === user.id || p.email === user.email)) {
        addNotification({
            type: "error",
            message: "User already in pending list",
        });
        return;
    }

    // Check if already a collaborator
    if (collaboratorsData?.collaborators.some(c => c.userEmail === user.email)) {
        addNotification({
            type: "error",
            message: "User already has access to this project",
        });
        return;
    }

    // Check if is the owner
    if (collaboratorsData?.owner.userEmail === user.email) {
        addNotification({
            type: "error",
            message: "Cannot share with project owner",
        });
        return;
    }

    // Add to pending list
    setPendingUsers(prev => [
        ...prev,
        {
            id: user.id,
            name: user.name,
            email: user.email,
            role: "viewer",
        },
    ]);

    // Clear search
    setSearchQuery("");
    setSearchResults([]);
    setSelectedIndex(-1);
};

const removeFromPending = (userId: string) => {
    setPendingUsers(prev => prev.filter(u => u.id !== userId));
};
```

#### 5. Sequential Submission

**Submit Button**:

- Disabled when `pendingUsers.length === 0`
- Label: "Share with {count} user(s)"
- Shows loading state during submission

**Logic**:

```typescript
const handleSubmitPending = async () => {
    setIsSubmitting(true);
    const errors: Array<{ name: string; error: string }> = [];

    for (const user of pendingUsers) {
        try {
            await ProjectSharingService.shareProject(projectId, {
                user_email: user.email,
                role: "viewer",
            });
        } catch (error) {
            errors.push({
                name: user.name,
                error: getErrorMessage(error),
            });
        }
    }

    setIsSubmitting(false);

    if (errors.length > 0) {
        const errorMsg = errors.map(e => `${e.name}: ${e.error}`).join(", ");
        addNotification({
            type: "error",
            message: `Failed to share: ${errorMsg}`,
        });
    } else {
        addNotification({
            type: "success",
            message: `Successfully shared with ${pendingUsers.length} user(s)`,
        });
        setPendingUsers([]);
    }

    // Refresh collaborators list
    await fetchCollaborators();
};
```

## UI Layout Structure

```tsx
<Dialog open={isOpen} onOpenChange={onClose}>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>Share Project</DialogTitle>
    </DialogHeader>

    {/* Mode Toggle */}
    <div className="flex items-center gap-2">
      <Switch checked={useTypeahead} onCheckedChange={setUseTypeahead} />
      <Label>{useTypeahead ? 'Search Users' : 'Manual Email Entry'}</Label>
    </div>

    {/* Conditional: Typeahead Mode */}
    {useTypeahead ? (
      <div className="space-y-4">
        {/* Search Input */}
        <div className="relative">
          <Input
            placeholder="Search by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          {isSearching && <Spinner className="absolute right-2 top-2" />}
        </div>

        {/* Search Results Dropdown */}
        {(searchResults.length > 0 || (searchQuery && !isSearching)) && (
          <Popover open>
            <PopoverContent>
              {searchResults.length > 0 ? (
                searchResults.map((user, index) => (
                  <div
                    key={user.id}
                    className={cn("p-2 cursor-pointer hover:bg-accent",
                      index === selectedIndex && "bg-accent")}
                    onClick={() => handleSelectUser(user)}
                  >
                    <div className="font-medium">{user.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {user.email}
                      {user.title && ` " ${user.title}`}
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-muted-foreground">
                  No users found
                </div>
              )}
            </PopoverContent>
          </Popover>
        )}

        {/* Pending Users List */}
        {pendingUsers.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2">
              Pending Invitations ({pendingUsers.length})
            </h4>
            {pendingUsers.map(user => (
              <div key={user.id} className="flex justify-between items-center p-2 border rounded mb-2">
                <div>
                  <div className="font-medium">{user.name}</div>
                  <div className="text-sm text-muted-foreground">{user.email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">Viewer</Badge>
                  <Button variant="ghost" size="sm" onClick={() => removeFromPending(user.id)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Submit Button */}
        <Button
          onClick={handleSubmitPending}
          disabled={pendingUsers.length === 0 || isSubmitting}
          className="w-full"
        >
          {isSubmitting
            ? 'Sharing...'
            : `Share with ${pendingUsers.length} user(s)`}
        </Button>
      </div>
    ) : (
      /* Email Mode - Keep Existing UI */
      <div className="space-y-4">
        <Input placeholder="user@example.com" value={email} onChange={...} />
        <Select value={selectedRole} onValueChange={setSelectedRole}>
          <SelectItem value="editor">Editor</SelectItem>
          <SelectItem value="viewer">Viewer</SelectItem>
        </Select>
        <Button onClick={handleInvite}>Invite</Button>
      </div>
    )}

    {/* Separator */}
    <Separator className="my-4" />

    {/* Current Access List (Unchanged) */}
    <div className="collaborators-list">
      {/* Owner + Collaborators */}
    </div>
  </DialogContent>
</Dialog>
```

## Implementation Details

### Debounced Search Hook

Check if `src/lib/hooks/useDebounce.ts` exists. If not, create:

```typescript
import { useEffect, useState } from "react";

export function useDebounce<T>(value: T, delay: number = 300): T {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(timer);
        };
    }, [value, delay]);

    return debouncedValue;
}
```

### Duplicate Prevention

Before adding to pending list, check against:

1. Existing pending users (by id or email)
2. Current collaborators (by userEmail)
3. Project owner (by userEmail)

Show user-friendly error notification for each case.

### Sequential Submission Strategy

```typescript
const handleSubmitPending = async () => {
    setIsSubmitting(true);
    const errors: Array<{ name: string; error: string }> = [];

    // Call API one by one
    for (const user of pendingUsers) {
        try {
            await ProjectSharingService.shareProject(projectId, {
                user_email: user.email,
                role: "viewer",
            });
        } catch (error) {
            errors.push({
                name: user.name,
                error: getErrorMessage(error),
            });
        }
    }

    setIsSubmitting(false);

    // Handle results
    if (errors.length > 0) {
        const failed = errors.map(e => e.name).join(", ");
        addNotification({
            type: "error",
            message: `Failed to add: ${failed}`,
        });
    } else {
        addNotification({
            type: "success",
            message: `Successfully shared with ${pendingUsers.length} user(s)`,
        });
        setPendingUsers([]);
    }

    // Refresh collaborator list
    await fetchCollaborators();
};
```

**Note**: No progress indication during submission. Just loading state on button.

### Reset on Dialog Open

```typescript
useEffect(() => {
    if (isOpen) {
        // Reset to email mode
        setUseTypeahead(false);
        setSearchQuery("");
        setSearchResults([]);
        setPendingUsers([]);
        setSelectedIndex(-1);
    }
}, [isOpen]);
```

## Acceptance Criteria

### Mode Toggle

- [ ] Toggle switch appears at top of "Add User" section
- [ ] Label shows "Search Users" when checked, "Manual Email Entry" when unchecked
- [ ] Defaults to email mode (unchecked) each time dialog opens
- [ ] Switching modes clears search/pending state

### Typeahead Search

- [ ] Search input appears in typeahead mode
- [ ] Minimum 2 characters required before search triggers
- [ ] API call is debounced (300ms delay)
- [ ] Loading spinner shows while `isSearching`
- [ ] Results dropdown appears below input
- [ ] Each result shows: Name on line 1, "Email " Title" on line 2 (omit title if null)
- [ ] Clicking result adds user to pending list

### Keyboard Navigation

- [ ] � Arrow Down moves selection down
- [ ] � Arrow Up moves selection up
- [ ] Selected item has highlighted background
- [ ] Enter key selects highlighted user
- [ ] Escape key clears results and search

### Pending Users List

- [ ] Section header shows "Pending Invitations (X)"
- [ ] Each user shows Name, Email, "Viewer" badge, and Remove button
- [ ] Remove button (X icon) removes user from pending list
- [ ] Section only visible when `pendingUsers.length > 0`

### Duplicate Prevention

- [ ] Cannot add same user twice to pending list (show error notification)
- [ ] Cannot add user who is already a collaborator (show error notification)
- [ ] Cannot add the project owner (show error notification)

### Submission

- [ ] "Share with X user(s)" button disabled when no pending users
- [ ] Button shows loading state during submission ("Sharing...")
- [ ] API calls made sequentially (one at a time)
- [ ] All users added with "viewer" role
- [ ] Success notification on completion
- [ ] Partial failures show error with failed user names
- [ ] Collaborators list refreshes after submission
- [ ] Pending list clears on success

### Email Mode (Preserved)

- [ ] Toggle to email mode shows original UI
- [ ] Email input, role dropdown, and Invite button work unchanged
- [ ] Single-user immediate invitation still works

### Error Handling

- [ ] "No users found" message when search returns empty array
- [ ] Network errors during search show notification
- [ ] Invalid/duplicate users show appropriate messages
- [ ] API errors during submission are collected and displayed

## Storybook Stories

Update `ShareDialog.stories.tsx` with new stories:

1. **TypeaheadMode**:
    - Dialog with toggle switched to typeahead
    - Empty search state

2. **TypeaheadWithResults**:
    - Search query active
    - Dropdown showing 3-4 user results

3. **TypeaheadWithPending**:
    - 2-3 users in pending list
    - Shows remove buttons

4. **TypeaheadNoResults**:
    - Search active but "No users found" message

Mock `PeopleService.searchPeople` to return fixture data.

## Technical Notes

### Dependencies to Check

- `@radix-ui/react-switch` - For toggle (may already exist via Shadcn)
- `@radix-ui/react-popover` - For dropdown (likely exists)
- `useDebounce` hook - Check if already in codebase

### Existing Patterns to Follow

1. Use `cn()` utility for conditional classNames
2. Use Lucide icons: `Search`, `X`, `Loader2`
3. Use `addNotification` from context for feedback
4. Use `getErrorMessage` for API error extraction
5. Follow Shadcn component patterns

### Edge Cases

- Search while previous search is loading: Cancel previous request (optional)
- Close dialog while submitting: Allow submission to complete (don't cancel)
- Empty pending list: Disable submit button
- All submissions fail: Show aggregated error, keep pending list

## Success Metrics

- Can search and add 5 users to pending list without issues
- Keyboard navigation feels smooth (no lag)
- Debounce prevents excessive API calls (max 1 per 300ms)
- Sequential submission completes successfully for 5+ users
- Toggle between modes works instantly
- Build succeeds: `npm run build-package && npm run lint`
- Storybook stories demonstrate all states

## Out of Scope (Future)

- Role selection in typeahead mode (hardcoded to Viewer)
- Persistent toggle preference
- Batch share API (backend doesn't support)
- Progress bar during sequential submission
- Cancel pending submissions
- Advanced search filters
- User avatars in results
- Pagination for search results
