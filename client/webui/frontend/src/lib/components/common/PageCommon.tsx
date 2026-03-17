import React from "react";

export const PAGE_COMMON_CLASSES = "w-full max-w-[1200px] leading-[21px]";

export const PageLabel = ({ children, required, className = "" }: { children: React.ReactNode; required?: boolean; className?: string }) => {
    return (
        <div className={`text-(--secondary-text-w50) ${className}`}>
            {children}
            {required && <span className="ml-1 text-(--accent-w100)">*</span>}
        </div>
    );
};

export const PageLabelWithValue = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`grid grid-rows-[auto_1fr] gap-2 ${className}`}>{children}</div>;
};

export const PageFooter = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => {
    return <div className={`flex h-16 items-center justify-end gap-4 border-t border-(--secondary-w20) px-8 ${className}`}>{children}</div>;
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
            <div className="text-xs font-semibold text-(--secondary-text-w50)">Metadata</div>
            <div className="space-y-1">
                {Object.entries(metadata).map(([key, value]) => (
                    <div key={key} className="text-xs">
                        <span className="font-medium text-(--secondary-text-w50)">{key}:</span> <span className="text-(--secondary-text-w50)">{String(value)}</span>
                    </div>
                ))}
            </div>
        </PageSection>
    );
};
