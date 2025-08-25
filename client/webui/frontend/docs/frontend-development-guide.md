# Frontend Development Guide

## Overview
This guide outlines the patterns, conventions, and best practices for developing frontend features in the Solace Agent Mesh web UI. The frontend follows React/TypeScript patterns with shadcn/ui components and CSS custom properties for theming.

## Architecture Patterns

### Component Structure
Follow this layered approach when creating new features:

1. **Types**: Define TypeScript interfaces in `src/lib/types/`
2. **API Hooks**: Create custom hooks for data fetching in `src/lib/hooks/`
3. **Components**: Build UI components in `src/lib/components/[feature]/`
4. **Pages**: Create page components that orchestrate the feature
5. **Navigation**: Wire up routing in `App.tsx`

### File Organization
```
src/lib/
├── types/
│   └── [feature].ts          # TypeScript interfaces
├── hooks/
│   └── use[Feature].ts       # Data fetching hooks
├── components/
│   ├── [feature]/
│   │   ├── index.ts          # Barrel exports
│   │   ├── [Feature]Page.tsx # Main page component
│   │   ├── [Feature]Dialog.tsx # Dialogs/modals
│   │   ├── [Feature]Card.tsx  # Individual item cards
│   │   └── [Feature]List.tsx  # Collection components
│   └── ui/
│       └── index.ts          # UI component exports
```

## Development Conventions

### 1. TypeScript Types
- Create interfaces that match backend DTOs exactly
- Add frontend-specific types as needed (e.g., form data, component props)
- Use proper optional/required field annotations

```typescript
// Backend DTO interface
export interface Project {
    id: string;
    name: string;
    description?: string | null;
    // ... other fields
}

// Frontend form interface
export interface ProjectFormData {
    name: string;
    description: string;
}
```

### 2. API Hooks Pattern
- Create custom hooks for all API interactions
- Include loading states, error handling, and local state management
- Use `authenticatedFetch` utility for API calls

```typescript
export const useProjects = (): UseProjectsReturn => {
    const [data, setData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    // Fetch, create, update methods
    // Return { data, isLoading, error, methods }
};
```

### 3. Component Patterns

#### Page Components
- Orchestrate the entire feature
- Handle state management and user interactions
- Connect hooks to UI components

#### Dialog/Modal Components
- Use react-hook-form for form handling
- Include proper validation with clear error messages
- Handle loading states during submission

#### List/Card Components
- Keep them focused and reusable
- Accept callback props for interactions
- Handle empty states gracefully

### 4. Theming Requirements

**CRITICAL: Never hardcode colors. Always use CSS custom properties.**

#### Correct Theming Approach
```typescript
// ✅ CORRECT - Use theme variables
className="bg-background text-foreground border"
className="text-muted-foreground hover:bg-accent"
```

#### Incorrect Approach
```typescript
// ❌ WRONG - Never hardcode colors
className="bg-white text-black border-gray-300"
className="text-gray-500 hover:bg-blue-100"
```

#### Available Theme Variables
- **Backgrounds**: `bg-background`, `bg-card`, `bg-accent`
- **Text**: `text-foreground`, `text-muted-foreground`, `text-destructive`
- **Borders**: `border` (uses CSS custom property)
- **Interactive**: `hover:bg-accent`, `hover:text-accent-foreground`

### 5. shadcn/ui Component Usage

#### Available Components
Check `src/lib/components/ui/index.ts` for all available components. Common ones include:
- Form components: `Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormMessage`
- Layout: `Card`, `CardHeader`, `CardTitle`, `CardContent`, `CardDescription`
- Interactive: `Button`, `Dialog`, `Input`, `Textarea`, `Badge`

#### Adding New Components
1. Install from shadcn/ui if not already available
2. Add exports to `src/lib/components/ui/index.ts`
3. Use consistent theming in the component

### 6. Form Handling

Use react-hook-form for all forms:

```typescript
const form = useForm<FormData>({
    defaultValues: { /* defaults */ },
});

// In JSX
<Form {...form}>
    <form onSubmit={form.handleSubmit(handleSubmit)}>
        <FormField
            control={form.control}
            name="fieldName"
            rules={{ required: "Field is required" }}
            render={({ field }) => (
                <FormItem>
                    <FormLabel>Label</FormLabel>
                    <FormControl>
                        <Input {...field} />
                    </FormControl>
                    <FormMessage />
                </FormItem>
            )}
        />
    </form>
</Form>
```

### 7. State Management

#### Loading States
- Show loading indicators during API calls
- Disable form inputs during submission
- Provide clear feedback to users

#### Error Handling
- Display user-friendly error messages
- Handle both API and validation errors
- Don't expose technical details to users

### 8. Navigation Integration

To add a new page to the navigation:

1. Add the navigation item to `src/lib/components/navigation/navigation.ts`
2. Import the page component in `App.tsx`
3. Add the route case in `renderMainContent()`

```typescript
// In navigation.ts
{
    id: "feature",
    label: "Feature",
    icon: IconComponent,
}

// In App.tsx
case "feature":
    return <FeaturePage />;
```

## Best Practices

### Code Quality
- Use TypeScript strictly - no `any` types
- Add proper error boundaries where needed
- Keep components focused and single-purpose
- Write self-documenting code with clear names

### Performance
- Use `useCallback` and `useMemo` for expensive operations
- Implement proper loading states
- Consider virtualization for long lists

### Accessibility
- Include proper ARIA labels
- Ensure keyboard navigation works
- Use semantic HTML elements
- Test with screen readers

### Testing Considerations
- Write components that are easy to test
- Keep business logic in hooks, not components
- Use dependency injection patterns where helpful

## Example: Complete Feature Implementation

For reference, see the projects feature implementation:
- Types: `src/lib/types/projects.ts`
- Hook: `src/lib/hooks/useProjects.ts`
- Components: `src/lib/components/projects/`
- Integration: `App.tsx` navigation setup

This follows all the patterns and conventions outlined in this guide and serves as a template for future feature development.