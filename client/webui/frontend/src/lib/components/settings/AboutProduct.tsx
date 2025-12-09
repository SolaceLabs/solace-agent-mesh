import React, { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableRow } from "@/lib/components/ui";
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
            return <div className="text-muted-foreground text-sm">Loading version information...</div>;
        }
        if (error) {
            return <div className="text-destructive text-sm">Error: {error}</div>;
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
                const data: VersionResponse = await api.chat.get("/api/v1/version");
                setVersionData(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Unknown error");
            } finally {
                setLoading(false);
            }
        };

        void fetchVersions();
    }, []);

    return (
        <div className="space-y-6">
            {/* Versions Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Application Versions</h3>
                </div>

                {renderVersionTable()}
            </div>
        </div>
    );
};
