# Cypress Testing for Solace Agent Mesh Community

This directory contains Cypress end-to-end tests for the Solace Agent Mesh Community frontend application.

## Directory Structure

- `e2e/`: Contains end-to-end test files
    - `chat-page.cy.ts`: Tests for chat page functionality
    - `agents-page.cy.ts`: Tests for agents page functionality
- `support/`: Contains support files like custom commands and configuration
    - `e2e.ts`: Main support file that imports all commands and sets up global configuration
    - `commands.ts`: Custom commands for testing library integration and navigation
    - `simple-session-commands.ts`: Session management for community application
    - `workflow-commands.ts`: Commands for testing React Flow workflow components

## Running Tests

To run the tests locally, you can use the following npm scripts:

### Open Cypress in interactive mode

```bash
npm run cypress:open
```

### Run Cypress tests headlessly

```bash
npm run cypress:run
```

## Testing Different Environments

### Local Development

By default, tests run against `http://localhost:3000` (Vite dev server):

```bash
npm run cypress:open
```

### Remote Environment

To run against a live URL, set the `CYPRESS_BASE_URL` environment variable:

```bash
CYPRESS_BASE_URL=https://your-deployed-app.com npm run cypress:open
```

## Writing Tests

Tests are written using Cypress and are located in the `e2e/` directory. Each test file should have the `.cy.ts` extension.

### Test Structure

Tests follow this structure pattern:

```typescript
describe("Feature Name", { tags: ["@community"] }, () => {
    beforeEach(() => {
        // Navigate to specific page
        cy.navigateToChat(); // or cy.navigateToAgents();
    });

    it("should do something", () => {
        cy.findByRole("button", { name: "Button Name" }).should("be.visible");
        // More assertions...
    });
});
```

### Available Test Tags

- `@community`: Tests applicable to the community version

## Custom Commands

Custom Cypress commands are available in `support/commands.ts`:

### Navigation Commands

- `cy.navigateToChat()`: Navigate to the chat page
- `cy.navigateToAgents()`: Navigate to the agents page

### Chat Commands

- `cy.startNewChat()`: Start a new chat session

### Session Commands

- `cy.ensureSamSession()`: Ensure application session is initialized

### Workflow Commands

- `cy.waitForWorkflowToLoad(options?)`: Wait for React Flow workflow to load
- `cy.waitForWorkflowNodes(expectedCount, options?)`: Wait for specific number of workflow nodes

## Testing Library Integration

Tests use `@testing-library/cypress` for accessible queries:

- `cy.findByRole()`: Find elements by ARIA role
- `cy.findByText()`: Find elements by text content
- `cy.findByTestId()`: Find elements by test ID
- `cy.findAllByRole()`: Find all elements by ARIA role

## Configuration

Cypress configuration is located in `cypress.config.js` in the root of the frontend directory.

### Key Configuration Options

- **Base URL**: `http://localhost:3000` (configurable via `CYPRESS_BASE_URL`)
- **Timeouts**: Extended timeouts for application loading and API responses
- **Retries**: 2 retries in run mode, 0 retries in open mode
- **Viewport**: 1280x720 default viewport
- **Video**: Enabled for debugging
- **Screenshots**: Enabled on test failures

## CI/CD Integration

Tests are configured for CI/CD with:

- JUnit reporter for test results
- Video recording for debugging
- Screenshot capture on failures
- Retry logic for flaky tests

## Best Practices

### Writing Tests

1. Use descriptive test names that explain the expected behavior
2. Use `@testing-library/cypress` queries for better accessibility
3. Add appropriate wait conditions for dynamic content
4. Test responsive design at different viewports
5. Use custom commands for common actions

### Debugging

1. Use `cy.log()` for debugging information
2. Take advantage of video recordings and screenshots
3. Use the interactive mode for test development
4. Check network requests in the Cypress DevTools

### Performance

1. Use `cy.session()` for session management
2. Implement appropriate wait strategies
3. Clean up test data when necessary
4. Use efficient selectors

## Troubleshooting

### Common Issues

1. **Elements not found**: Ensure selectors match the actual DOM structure
2. **Timing issues**: Add appropriate wait conditions
3. **Session problems**: Verify `cy.ensureSamSession()` is working correctly
4. **Network timeouts**: Check if the application is running and accessible

### Environment Setup

Ensure the following are installed:

- Node.js (>=20.8.10)
- npm or yarn
- Cypress dependencies (`npm ci`)

### Development Server

Make sure the development server is running:

```bash
npm run dev
```

Then run Cypress tests in another terminal.
