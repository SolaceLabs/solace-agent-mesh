# Global Projects Feature

## Overview
Enable organization-wide project templates that users can discover and copy to their personal workspace.

## Problem Statement
Currently, all projects are private to individual users. There's no way to share project setups across the organization or provide standardized templates for common use cases.

## Solution
Introduce "Global Projects" - organization-wide project templates that any user can browse, preview, and copy to create their own instance.

## User Stories

### Template Creator
- As an admin/power user, I want to create project templates that others in my org can use
- As a template creator, I want to see how many people have used my templates

### Template Consumer  
- As a user, I want to browse available project templates in my organization
- As a user, I want to copy a template to create my own project based on it
- As a user, I want my copied project to be completely independent from the original

## Technical Design

### Database Changes
Add to existing `Project` model:
- `is_global` (Boolean) - distinguishes templates from user projects
- `template_id` (String, nullable FK) - links copied projects back to original template
- `created_by_user_id` (String) - tracks who created the template

### Project Types
1. **User Original Project**: `is_global=false, template_id=null`
2. **User Copied Project**: `is_global=false, template_id=<original_id>`  
3. **Global Template**: `is_global=true, template_id=null, user_id=null`

### Copy Behavior
- Copying creates empty project (no sessions or messages)
- User gets full ownership of their copy
- Copy is completely independent from template

## User Experience

### Template Discovery
- New "Browse Templates" section in UI
- List view with template name, description, creator, usage count
- Search and filter capabilities

### Copy Flow
1. User browses available templates
2. Clicks "Use This Template"
3. Provides new project name (pre-filled with template name)
4. Creates personal copy in their project list

### Attribution
- Copied projects show "Based on [Template Name]"
- Template creators can see usage analytics

## Future Enhancements
- Template categories and tagging
- Template versioning and update notifications  
- Approval workflow for creating global templates
- Template sync capabilities

## Success Metrics
- Number of global templates created
- Template usage/copy rates
- User adoption of template feature
- Reduction in duplicate project setups

## Implementation Phases

### Phase 1: Core Functionality
- Database schema updates
- Basic copy functionality
- Simple template browsing UI

### Phase 2: Enhanced Discovery
- Search and filtering
- Categories and tags
- Usage analytics

### Phase 3: Advanced Features
- Template versioning
- Update notifications
- Enhanced governance