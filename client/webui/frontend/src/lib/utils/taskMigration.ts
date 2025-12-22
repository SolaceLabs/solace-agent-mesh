import type { ParsedTaskData } from "@/lib/types/storage";

export const CURRENT_SCHEMA_VERSION = 1;

// Migration function type
type MigrationFunction = (task: ParsedTaskData) => ParsedTaskData;

/**
 * Migration V0 -> V1: Add schema_version field to tasks
 */
const migrateV0ToV1: MigrationFunction = task => {
    return {
        ...task,
        taskMetadata: {
            ...task.taskMetadata,
            schema_version: 1,
        },
    };
};

/**
 * Future migration: V1 -> V2
 * Uncomment and implement when needed
 */
// const migrateV1ToV2: MigrationFunction = (task) => {
//     return {
//         ...task,
//         taskMetadata: {
//             ...task.taskMetadata,
//             schema_version: 2,
//             // Add new fields here
//         },
//     };
// };

/**
 * Registry of migration functions
 * Key = source version, Value = migration function to next version
 */
const MIGRATIONS: Record<number, MigrationFunction> = {
    0: migrateV0ToV1,
    // 1: migrateV1ToV2,
};

/**
 * Apply all necessary migrations to bring a task to the current schema version
 * @param task - The task to migrate
 * @returns The migrated task at the current schema version
 */
export const migrateTask = (task: ParsedTaskData): ParsedTaskData => {
    const version = task.taskMetadata?.schema_version ?? 0;

    // Already at current version
    if (version >= CURRENT_SCHEMA_VERSION) {
        return task;
    }

    // Apply migrations sequentially
    let migratedTask = task;
    for (let v = version; v < CURRENT_SCHEMA_VERSION; v++) {
        const migrationFunc = MIGRATIONS[v];

        if (migrationFunc) {
            migratedTask = migrationFunc(migratedTask);
            console.log(`[Migration] Migrated task ${task.taskId} from v${v} to v${v + 1}`);
        } else {
            console.warn(`[Migration] No migration function found for version ${v}`);
        }
    }

    return migratedTask;
};

/**
 * Migrate an array of tasks
 * @param tasks - Array of tasks to migrate
 * @returns Array of migrated tasks
 */
export const migrateTasks = (tasks: ParsedTaskData[]): ParsedTaskData[] => {
    return tasks.map(migrateTask);
};

/**
 * Check if a task needs migration
 * @param task - The task to check
 * @returns true if migration is needed
 */
export const needsMigration = (task: ParsedTaskData): boolean => {
    const version = task.taskMetadata?.schema_version ?? 0;
    return version < CURRENT_SCHEMA_VERSION;
};

/**
 * Get the current schema version
 * @returns The current schema version number
 */
export const getCurrentSchemaVersion = (): number => {
    return CURRENT_SCHEMA_VERSION;
};
