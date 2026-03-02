/// <reference types="cypress" />
import "@testing-library/cypress/add-commands";

import type { ByRoleOptions } from "@testing-library/dom";

/* eslint-disable @typescript-eslint/no-namespace */
declare global {
    namespace Cypress {
        interface Chainable {
            // @testing-library/cypress commands
            findByText(text: string | RegExp): Chainable;
            findByRole(role: string, options?: Partial<ByRoleOptions>): Chainable;
            findAllByRole(role: string, options?: Partial<ByRoleOptions>): Chainable;
            findByTestId(testId: string): Chainable;
            findByDisplayValue(value: string | RegExp): Chainable;

            // custom commands for community application
            startNewChat(): Chainable;
            navigateToChat(): Chainable;
            navigateToAgents(): Chainable;
            navigateToWorkflows(): Chainable;
            ensurePanelExpanded(): Chainable;
        }
        interface SuiteConfigOverrides {
            tags?: string[];
        }
    }
}

Cypress.Commands.add("startNewChat", () => {
    cy.navigateToChat();
    cy.findAllByRole("button", { name: "Start New Chat Session" }).filter(":visible").should("have.length", 1).click();

    // Check if dialog appears (when persistenceEnabled is false)
    cy.get("body").then($body => {
        if ($body.find('[role="dialog"]').length > 0) {
            // Dialog exists, wait for it to be visible and click confirmation
            cy.findByRole("dialog").should("be.visible");
            cy.findByRole("button", { name: "Start New Chat" }).should("be.visible").click();
        }
        // If no dialog exists, the new chat was already started by the button click
    });
});

Cypress.Commands.add("navigateToChat", () => {
    cy.log("Navigating to Chat page");
    cy.findByRole("button", { name: "Chat" }).should("be.visible").click();
    cy.url().should("include", "/");
});

Cypress.Commands.add("navigateToAgents", () => {
    cy.log("Navigating to Agents page");
    cy.findByRole("button", { name: "Agent Mesh" }).should("be.visible").click();
});

Cypress.Commands.add("navigateToWorkflows", () => {
    cy.log("Navigating to Workflows page");
    // First navigate to Agent Mesh page
    cy.findByRole("button", { name: "Agent Mesh" }).should("be.visible").click();
    // Then click the Workflows tab
    cy.findByRole("tab", { name: /workflows/i })
        .should("be.visible")
        .click();
    cy.url().should("include", "tab=workflows");
});

/**
 * Ensures the side panel is in an expanded state.
 * If the panel is collapsed, clicks the expand button and waits for expansion.
 * If already expanded, does nothing.
 */
Cypress.Commands.add("ensurePanelExpanded", () => {
    cy.get("body").then($body => {
        if ($body.find('[data-testid="expandPanel"]').length > 0) {
            cy.log("Panel is collapsed, expanding it");
            cy.get('[data-testid="expandPanel"]').should("be.visible").click();
            // Wait for panel to be expanded by checking for collapsePanel button
            cy.get('[data-testid="collapsePanel"]', { timeout: 5000 }).should("be.visible");
            cy.log("Panel expanded successfully");
        } else {
            cy.log("Panel already expanded");
        }
    });
});

export {};
