import React, { useState } from "react";

import { useChatContext, useDownload } from "@/lib/hooks";
import { formatBytes } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";

import { ArtifactDetails } from "./ArtifactDetails";
import { getFileIcon } from "../file/fileUtils";

interface ArtifactCardProps {
    artifact: ArtifactInfo;
    isPreview?: boolean;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, isPreview }) => {
    const { openDeleteModal, setPreviewArtifact } = useChatContext();
    const { onDownload } = useDownload();

    const [isExpanded, setIsExpanded] = useState(false);

    const onDelete = () => {
        if (isPreview) {
            setPreviewArtifact(null);
        }
        openDeleteModal(artifact);
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const renderSchema = (schema: any): React.ReactNode => {
        if (!schema || (typeof schema === "object" && Object.keys(schema).length === 0)) {
            return <span>Not available</span>;
        }

        const renderStructure = (structure: unknown, depth = 0): React.ReactNode => {
            if (typeof structure === "string") {
                return <span>{structure}</span>;
            }
            if (Array.isArray(structure)) {
                return (
                    <>
                        [{structure.length > 0 && renderStructure(structure[0], depth + 1)}
                        {structure.length > 1 && <span>, ...</span>}]
                    </>
                );
            }
            if (typeof structure === "object" && structure !== null) {
                return (
                    <div className={`ml-${depth * 2} border-l pl-2`}>
                        {Object.entries(structure).map(([key, value], index) => (
                            <div key={index} className="text-xs">
                                <span className="font-semibold">{key}:</span> {renderStructure(value, depth + 1)}
                            </div>
                        ))}
                    </div>
                );
            }
            return String(structure);
        };

        return (
            <div className="mt-1 space-y-0.5">
                {typeof schema === "object" && schema.type && (
                    <p>
                        <strong>Type:</strong> {schema.type} {schema.inferred && <span className="text-xs">(inferred)</span>}
                    </p>
                )}
                {typeof schema === "object" && schema.columns && (
                    <p>
                        <strong>Columns:</strong> {schema.columns.join(", ")}
                    </p>
                )}
                {typeof schema === "object" && schema.structure && (
                    <div>
                        <strong>Structure:</strong>
                        {renderStructure(schema.structure)}
                    </div>
                )}
                {typeof schema === "object" && schema.error && (
                    <p className="text-[var(--color-error-wMain)]">
                        <strong>Schema Error:</strong> {schema.error}
                    </p>
                )}
                {typeof schema === "string" && <p>{schema}</p>}
            </div>
        );
    };

    return (
        <div
            className={`group relative w-full border-b px-4 py-3 transition-all duration-150 ${isPreview ? "" : "cursor-pointer hover:bg-[var(--accent-background)]"}`}
            onClick={e => {
                e.stopPropagation();
                setPreviewArtifact(artifact);
            }}
            onKeyDown={e => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    e.stopPropagation();
                    setPreviewArtifact(artifact);
                }
            }}
            tabIndex={0}
            role="button"
            aria-expanded={isExpanded}
        >
            <div className="flex items-start space-x-2">
                <div className="flex-shrink-0 pt-0.5">{getFileIcon(artifact, "h-4 w-4 flex-shrink-0")}</div>
                <div className="min-w-0 flex-grow">
                    <ArtifactDetails artifactInfo={artifact} isExpanded={isExpanded} onDelete={onDelete} onDownload={onDownload} setIsExpanded={setIsExpanded} isPreview={isPreview} />
                    {isExpanded && (
                        <div className={`text-xs`}>
                            <div className="mt-1 text-xs break-words whitespace-pre-wrap italic">{artifact.description || "No description."}</div>
                            <div className="mt-2 space-y-1 pt-2">
                                <div>
                                    <strong>Size: </strong>
                                    {formatBytes(artifact.size)}
                                </div>
                                {artifact.uri && (
                                    <div>
                                        <strong>URI: </strong>
                                        <span className="break-all">{artifact.uri || "None"}</span>
                                    </div>
                                )}
                                {artifact.schema && <div>{renderSchema(artifact.schema)}</div>}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
