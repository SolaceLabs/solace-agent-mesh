export const CYPRESS_TAG = "cypress-";

export const generateName = () => `${CYPRESS_TAG}-${Math.random().toString(36).substring(2, 10)}`;
