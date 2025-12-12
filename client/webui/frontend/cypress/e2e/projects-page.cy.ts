import { generateName } from "cypress/support/utils";

describe("Projects Page - Navigation and Layout", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToProjects();
        cy.deleteCypressProjects();
    });

    afterEach(() => {
        cy.deleteCypressProjects();
    });

    it("should create a project and verify its details", () => {
        const projectName = generateName();

        cy.findByRole("button", { name: "Create New Project" }).click();

        cy.findByLabelText(/Project Name/i).type(projectName);

        cy.findByLabelText(/Description/i).type("This is a test project created by Cypress.");

        cy.findByRole("button", { name: "Create Project" }).click();

        cy.findAllByText(projectName).should("have.length", 2);

        cy.findByRole("heading", { name: "Instructions" })
            .parent()
            .parent()
            .within(() => {
                cy.findByRole("button", { name: "Edit" }).click();
            });

        cy.findByRole("dialog", { name: "Edit Project Instructions" }).within(() => {
            cy.get("textarea").type("These are the updated instructions for the project.");

            cy.findByRole("button", { name: "Save" }).click();
        });

        cy.fixture("test-upload.txt").then(fileContent => {
            // 1. Upload the file
            cy.get('input[type="file"]').selectFile(
                {
                    contents: Cypress.Buffer.from(fileContent),
                    fileName: "test-upload.txt",
                    mimeType: "text/plain",
                },
                { force: true }
            );

            cy.findByRole("dialog", { name: "Upload Files to Project" }).within(() => {
                cy.contains("p", "test-upload.txt").closest("div[data-slot='card-content']").find("textarea").type("Description for the file");

                cy.findByRole("button", { name: /Upload 1 File\(s\)/i }).click();
            });
        });

        cy.findByRole("heading", { name: "Chats" })
            .parent()
            .findByRole("button", { name: /New Chat/i })
            .click();

        cy.url().should("include", "/chat");

        cy.contains('[data-slot="badge"]', projectName).should("be.visible");

        cy.findByTestId("expandPanel").click();

        cy.findByText("test-upload.txt").should("be.visible");

        cy.findByText("Description for the file").should("be.visible");
    });
});
