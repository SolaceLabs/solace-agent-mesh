import { Button } from "@/lib/components/ui";

export const ModelsOnboardingView = ({ title, description, onAddModel }: { title: string; description: string; onAddModel?: () => void }) => {
    return (
        <div className="flex h-full items-center justify-center">
            <div className="flex max-w-2xl flex-col items-center gap-6 px-6 text-center">
                <h2 className="text-xl font-semibold">{title}</h2>
                <p className="text-(--secondary-text-w50)">{description}</p>
                <div className="flex flex-col items-center gap-3">
                    <Button onClick={onAddModel} disabled={!onAddModel}>
                        <span className="mr-2">+</span> Add Model
                    </Button>
                    <Button variant="link" className="h-auto p-0 text-sm">
                        Learn about managing models →
                    </Button>
                </div>
            </div>
        </div>
    );
};
