export const CYPRESS_PREFIX = "cypress-";

export const generateName = () => `${CYPRESS_PREFIX}-${Math.random().toString(36).substring(2, 10)}`;
