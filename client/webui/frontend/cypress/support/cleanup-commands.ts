declare global {
    namespace Cypress {
        interface Chainable {
            cleanupAllSessions(): Chainable<void>;
        }
    }
}

const PAGE_SIZE = 100;
const MAX_ROUNDS = 100;

interface SessionListResponse {
    data?: Array<{ id: string }>;
}

const cleanupRound = (round: number) => {
    if (round > MAX_ROUNDS) {
        cy.log(`cleanupAllSessions: hit safety limit of ${MAX_ROUNDS} rounds, stopping`);
        return;
    }

    cy.request({
        method: "GET",
        url: `/api/v1/sessions?pageNumber=1&pageSize=${PAGE_SIZE}`,
        failOnStatusCode: false,
    }).then(response => {
        if (response.status !== 200) {
            cy.log(`cleanupAllSessions: list returned status ${response.status}, skipping`);
            return;
        }

        const sessions = (response.body as SessionListResponse).data ?? [];
        if (sessions.length === 0) {
            cy.log("cleanupAllSessions: no sessions remaining");
            return;
        }

        cy.log(`cleanupAllSessions round ${round}: deleting ${sessions.length} session(s)`);
        sessions.forEach(s => {
            cy.request({
                method: "DELETE",
                url: `/api/v1/sessions/${s.id}`,
                failOnStatusCode: false,
            });
        });

        cleanupRound(round + 1);
    });
};

Cypress.Commands.add("cleanupAllSessions", () => {
    cy.log("cleanupAllSessions: starting");
    cleanupRound(1);
});

export {};
