// E2E test covering the complete workflow user journey
describe.skip("Workflows Page - End-to-End User Journey", { tags: ["@community"] }, () => {
    it("should complete full workflow interaction flow", () => {
        cy.log("Navigating to workflows page");
        cy.navigateToWorkflows();

        // Verify we're on the workflows page
        cy.url().should("include", "tab=workflows");

        cy.log("Verifying workflows table displays");

        // Verify table is visible with workflows
        cy.findByRole("table", { name: "Workflows" }).should("be.visible");

        cy.log("Clicking workflow to open visualization");

        // Click CompleteOrderWorkflow to open visualization
        cy.findByRole("table", { name: "Workflows" }).within(() => {
            cy.findByRole("button", { name: "CompleteOrderWorkflow" }).click();
        });

        // Verify navigation to visualization
        cy.url().should("include", "/agents/workflows/");

        cy.log("Verifying workflow visualization renders");

        // Verify visualization renders with Start and End nodes
        cy.findByRole("region", { name: "Workflow visualization" })
            .should("exist")
            .within(() => {
                cy.findByText("Start").should("exist");
                cy.findByText("OrderValidator").should("exist");
                cy.findByText("End").should("exist");
            });

        cy.log("Opening node details panel");

        // Click OrderValidator agent node to open details panel
        cy.findByRole("region", { name: "Workflow visualization" }).within(() => {
            cy.findByText("OrderValidator").click();
        });

        // Verify node details panel opens and displays correct agent data
        cy.findByRole("complementary", { name: "Node details panel" })
            .should("be.visible")
            .within(() => {
                cy.findByText("OrderValidator").should("exist");
                cy.findByText("validate_order").should("exist");
            });

        cy.log("Opening workflow details panel");

        // Click Open Workflow Details button (closes node panel, opens workflow panel)
        cy.findByRole("button", { name: /Open Workflow Details/i }).click();

        // Verify workflow details panel opens and node panel closes
        cy.findByRole("complementary", { name: "Workflow details panel" }).should("be.visible");
        cy.findByRole("complementary", { name: "Node details panel" }).should("not.exist");

        cy.log("Closing workflow details panel");

        // Close workflow details panel
        cy.findByRole("complementary", { name: "Workflow details panel" }).within(() => {
            cy.findByRole("button", { name: "Close" }).click();
        });

        // Verify panel is closed
        cy.findByRole("complementary", { name: "Workflow details panel" }).should("not.exist");

        cy.log("Workflow e2e journey completed successfully");
    });
});
