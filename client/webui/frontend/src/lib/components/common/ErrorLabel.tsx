export const ErrorLabel = ({ message, className }: { message?: string; className?: string }) => {
    return message ? <div className={`text-xs text-(--error-wMain) ${className}`}>{message}</div> : null;
};
