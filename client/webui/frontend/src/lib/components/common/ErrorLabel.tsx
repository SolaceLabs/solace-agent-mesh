export const ErrorLabel = ({ message, className }: { message?: string; className?: string }) => {
    return message ? <div className={`text-xs text-(--color-error-wMain) ${className}`}>{message}</div> : null;
};
