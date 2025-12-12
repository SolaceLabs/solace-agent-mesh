/// <reference types="cypress" />

declare global {
    namespace Cypress {
        interface Chainable {
            createProject(name: string, description: string): Chainable<void>;
            addProjectInstructions(instructions: string): Chainable<void>;
            uploadFileToProject(fileContent: any, fileName: string, description: string): Chainable<void>;
        }
    }
}

Cypress.Commands.add("createProject", (name, description) => {
    cy.findByRole("button", { name: "Create New Project" }).click();
    cy.findByLabelText(/Project Name/i).type(name);
    cy.findByLabelText(/Description/i).type(description);
    cy.findByRole("button", { name: "Create Project" }).click();
});

Cypress.Commands.add("addProjectInstructions", instructions => {
    cy.findByRole("heading", { name: "Instructions" })
        .parent()
        .parent()
        .within(() => {
            cy.findByRole("button", { name: "Edit" }).click();
        });

    cy.findByRole("dialog", { name: "Edit Project Instructions" }).within(() => {
        cy.get("textarea").type(instructions);
        cy.findByRole("button", { name: "Save" }).click();
    });
});

Cypress.Commands.add("uploadFileToProject", (fileContent, fileName, description) => {
    cy.get('input[type="file"]').selectFile(
        {
            contents: Cypress.Buffer.from(fileContent),
            fileName: fileName,
            mimeType: "text/plain",
        },
        { force: true }
    );

    cy.findByRole("dialog", { name: "Upload Files to Project" }).within(() => {
        cy.contains("p", fileName).closest("div[data-slot='card-content']").find("textarea").type(description);

        cy.findByRole("button", { name: /Upload 1 File\(s\)/i }).click();
    });
});

export {};
