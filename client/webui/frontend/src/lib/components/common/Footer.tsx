export const Footer = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`flex h-16 items-center justify-end gap-4 border-t px-8 ${className}`}>{children}</div>;
};
