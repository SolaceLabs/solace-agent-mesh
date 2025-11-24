/**
 * Reserved slash commands that cannot be used as prompt shortcuts
 */
export const RESERVED_COMMANDS = ['create-template'] as const;

export type ReservedCommand = typeof RESERVED_COMMANDS[number];

export function isReservedCommand(command: string): boolean {
    return RESERVED_COMMANDS.includes(command as ReservedCommand);
}