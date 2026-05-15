import "./commands";
import "./workflow-commands";
import "./simple-session-commands";
import "./cleanup-commands";

// Hide fetch/XHR requests in the command log
const app = window.top;
if (app && !app.document.head.querySelector("[data-hide-command-log-request]")) {
    const style = app.document.createElement("style");
    style.innerHTML = ".command-name-request, .command-name-xhr { display: none }";
    style.setAttribute("data-hide-command-log-request", "");
    app.document.head.appendChild(style);
}

before(() => {
    // Wipe leftover sessions from prior runs before this spec begins.
    cy.ensureSamSession();
    cy.cleanupAllSessions();
});

beforeEach(() => {
    // Ensure SAM application session exists (without authentication)
    cy.ensureSamSession();

    // Visit the application (no login required for community version)
    cy.visit("/");
});

after(() => {
    // Leave the env clean for the next consumer.
    cy.cleanupAllSessions();
});
