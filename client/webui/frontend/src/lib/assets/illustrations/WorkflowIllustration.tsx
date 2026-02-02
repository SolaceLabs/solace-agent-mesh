import { useThemeContext } from "@/lib/hooks/useThemeContext";
import workflowDark from "../images/workflowDark.svg";
import workflowLight from "../images/workflowLight.svg";

interface WorkflowIllustrationProps {
    width?: number;
    height?: number;
}

export function WorkflowIllustration({ width, height }: WorkflowIllustrationProps) {
    const { currentTheme } = useThemeContext();

    // Note: the svgs have hard-coded colours and will not adjust to theme changes
    return <img src={currentTheme === "dark" ? workflowDark : workflowLight} alt="Workflow illustration" width={width} height={height} className="h-auto w-auto" />;
}
