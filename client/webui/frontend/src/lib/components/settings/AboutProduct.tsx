import React, { useEffect, useState } from "react";
import { Spinner, Table, TableBody, TableCell, TableRow } from "@/lib/components/ui";
import { getErrorMessage } from "@/lib/utils/api";
import { MessageBanner } from "../common";
import { api } from "@/lib/api";

interface Product {
    id: string;
    name: string;
    description: string;
    version: string;
    dependencies?: Record<string, string>;
}

interface VersionResponse {
    products: Product[];
}

export const AboutProduct: React.FC = () => {
    const [versionData, setVersionData] = useState<VersionResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const renderVersionTable = () => {
        if (loading) {
            return <Spinner className="mt-8" />;
        }
        if (error) {
            return <MessageBanner variant="error" message={`Error loading application information. ${error}`} />;
        }
        if (!versionData) {
            return null;
        }
        return (
            <Table>
                <TableBody>
                    {versionData.products
                        .toSorted((a, b) => a.name.localeCompare(b.name))
                        .map(product => (
                            <TableRow key={product.id} className="hover:bg-transparent">
                                <TableCell className="font-medium">{product.name}</TableCell>
                                <TableCell>{product.version}</TableCell>
                            </TableRow>
                        ))}
                </TableBody>
            </Table>
        );
    };

    useEffect(() => {
        const fetchVersions = async (): Promise<void> => {
            try {
                const data: VersionResponse = await api.webui.get("/api/v1/version");
                setVersionData(data);
            } catch (err) {
                setError(getErrorMessage(err));
            } finally {
                setLoading(false);
            }
        };

        void fetchVersions();
    }, []);

    return (
        <div className="space-y-6">
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <div className="text-lg font-semibold">Application Versions</div>
                </div>

                {renderVersionTable()}
            </div>
        </div>
    );
};
