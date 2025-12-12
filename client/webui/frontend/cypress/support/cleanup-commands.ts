/// <reference types="cypress" />
import { CYPRESS_PREFIX } from "./utils";

declare global {
    namespace Cypress {
        interface Chainable {
            deleteCypressProjects(): Chainable<void>;
        }
    }
}

Cypress.Commands.add("deleteCypressProjects", () => {
    cy.log(`Cleaning up '${CYPRESS_PREFIX}' projects...`);

    cy.request("GET", "/api/v1/projects").then(response => {
        const projects = response.body.projects || [];

        const projectsToDelete = projects.filter((project: any) => project.name.startsWith(CYPRESS_PREFIX));

        cy.log(`Found ${projectsToDelete.length} projects to delete.`);

        projectsToDelete.forEach((project: any) => {
            cy.request({
                method: "DELETE",
                url: `/api/v1/projects/${project.id}`,
                failOnStatusCode: false,
            });
        });
    });
});

export {};
