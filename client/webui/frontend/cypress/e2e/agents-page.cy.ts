describe("Agents Page - Agent Cards Display", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToAgents();
    });

    it("should support searching and finding agents", () => {
        cy.findByTestId("agentSearchInput").should("be.visible").type("Orch");
        cy.findByText("Click for details").should("be.visible");
    });

    it("should support searching and not finding agents", () => {
        cy.findByTestId("agentSearchInput").should("be.visible").type("ImposterAgent");
        cy.findByText("Click for details").should("not.exist");
        cy.findByRole("button", { name: "Clear Filter" }).should("be.visible").click();
        cy.findByTestId("agentSearchInput").should("be.visible").should("have.value", "");
    });
});
