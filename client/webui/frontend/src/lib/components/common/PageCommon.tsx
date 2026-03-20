import React from "react";

export const PageLabel = ({ children, required, className = "" }: { children: React.ReactNode; required?: boolean; className?: string }) => {
    return (
        <div className={`text-sm font-medium text-(--secondary-text-wMain) ${className}`}>
            {children}
            {required && <span className="ml-1 text-(--accent-w100)">*</span>}
        </div>
    );
};

export const PageValue = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`text-sm ${className}`}>{children}</div>;
};

export const PageLabelWithValue = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`grid grid-rows-[auto_1fr] gap-2 ${className}`}>{children}</div>;
};

export const PageSection = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`flex flex-col gap-2 ${className}`}>{children}</div>;
};

export const PageContentWrapper = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return (
        <div className={`flex-1 overflow-y-auto p-8 leading-5 ${className}`}>
            <div className="flex flex-col gap-8">{children}</div>
        </div>
    );
};

export const Metadata = ({ metadata }: { metadata: Record<string, string | number> }) => {
    return (
        <PageSection className="gap-2 border-t border-(--secondary-w20) pt-6">
            <div className="text-xs font-semibold text-(--secondary-text-wMain)">Metadata</div>
            <div className="space-y-1">
                {Object.entries(metadata).map(([key, value]) => (
                    <div key={key} className="text-xs">
                        <span className="font-medium text-(--secondary-text-wMain)">{key}:</span> <span className="text-(--secondary-text-wMain)">{String(value)}</span>
                    </div>
                ))}
            </div>
        </PageSection>
    );
};

export const ErrorLabel = ({ children }: { children: React.ReactNode }) => <div className="text-xs text-(--error-w100)">{children}</div>;
