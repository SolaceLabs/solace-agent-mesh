import React from "react";
import { FileText, GraduationCap, Github, ExternalLink } from "lucide-react";

export const HelpSettings: React.FC = () => {
    const helpLinks = [
        {
            icon: <FileText className="size-5" />,
            title: "Documentation",
            description: "Read the complete documentation",
            url: "https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/",
        },
        {
            icon: <GraduationCap className="size-5" />,
            title: "Tutorials",
            description: "Learn with step-by-step guides",
            url: "#",
        },
        {
            icon: <Github className="size-5" />,
            title: "GitHub",
            description: "View source code and contribute",
            url: "https://github.com/SolaceLabs/solace-agent-mesh",
        },
    ];

    return (
        <div className="space-y-4">
            {helpLinks.map((link, index) => (
                <button
                    key={index}
                    onClick={() => {
                        if (link.url !== "#") {
                            window.open(link.url, "_blank");
                        }
                    }}
                    className="hover:bg-accent flex w-full items-center justify-between rounded-lg border p-4 transition-colors"
                >
                    <div className="flex items-center gap-3">
                        {link.icon}
                        <div className="text-left">
                            <div className="text-sm font-medium">{link.title}</div>
                            <p className="text-muted-foreground text-xs">{link.description}</p>
                        </div>
                    </div>
                    <ExternalLink className="text-muted-foreground size-4" />
                </button>
            ))}
        </div>
    );
};
