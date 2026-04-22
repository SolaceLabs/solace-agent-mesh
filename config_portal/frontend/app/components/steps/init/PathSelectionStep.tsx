import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import Button from "../../ui/Button";
import { StepComponentProps } from "../../InitializationFlow";
import { submitInitConfig } from "../../../common/submitConfig";

type PathType = "quick" | "advanced";

const CheckIcon = () => (
  <svg
    className="w-4 h-4 mr-1.5 text-green-500"
    fill="currentColor"
    viewBox="0 0 20 20"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
      clipRule="evenodd"
    ></path>
  </svg>
);

const SparkleIcon = () => (
  <Sparkles className="w-4 h-4 mr-1.5 text-solace-green flex-shrink-0" />
);

const Spinner = () => (
  <div className="flex items-center space-x-2">
    <svg
      className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      ></circle>
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
    <span>Initializing...</span>
  </div>
);

type PathOption = {
  title: string;
  timeEstimate: string;
  timeColor: string;
  description: string;
  features: string[];
  featureIcon: "check" | "sparkle";
  actionLabel: string;
};

const pathOptions: Record<PathType, PathOption> = {
  quick: {
    title: "Get Started Quickly",
    timeEstimate: "2 minutes",
    timeColor: "green",
    description: "Automatically setup Solace Agent Mesh with sensible defaults.",
    features: [
      "Broker settings configured for you",
      "Main orchestrator ready out of the box",
      "Web UI Gateway pre-configured",
    ],
    featureIcon: "sparkle",
    actionLabel: "Initialize",
  },
  advanced: {
    title: "Advanced Setup",
    timeEstimate: "10 minutes",
    timeColor: "blue",
    description: "Take full control over all configuration options",
    features: [
      "Set namespaces for topic prefixes",
      "Specify broker settings",
      "Configure main orchestrator",
      "Configure Web UI Gateway",
    ],
    featureIcon: "check",
    actionLabel: "Continue",
  },
};

const commonOutcomes = [
  "Ready-to-use Solace Agent Mesh with basic capabilities",
  "Chat Interface for immediate testing",
  "Foundation for adding more agents later",
];

const PathOptionCard = ({
  pathType,
  isSelected,
  isSubmitting,
  onSelect,
  onAction,
}: {
  pathType: PathType;
  isSelected: boolean;
  isSubmitting: boolean;
  onSelect: () => void;
  onAction: () => void;
}) => {
  const option = pathOptions[pathType];
  const showAction = isSelected;
  return (
    <div
      role="button"
      tabIndex={0}
      className={`
        border rounded-lg p-6 cursor-pointer transition-all
        ${
          isSelected
            ? "border-solace-green bg-solace-green/10 shadow-md"
            : "border-gray-200 hover:border-solace-green/50 hover:bg-gray-50"
        }
      `}
      onClick={onSelect}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xl font-bold text-solace-blue">{option.title}</h3>
        <span
          className={`bg-${option.timeColor}-100 text-${option.timeColor}-800 text-xs font-medium px-2.5 py-0.5 rounded`}
        >
          {option.timeEstimate}
        </span>
      </div>
      <p className="text-gray-600 mb-4">{option.description}</p>

      {option.features.length > 0 && (
        <ul className="space-y-2 text-sm text-gray-600 mb-4">
          {option.features.map((feature) => (
            <li key={feature} className="flex items-center">
              {option.featureIcon === "sparkle" ? <SparkleIcon /> : <CheckIcon />}
              {feature}
            </li>
          ))}
        </ul>
      )}

      <div
        className={`
          flex justify-end transition-opacity duration-200
          ${showAction ? "opacity-100" : "opacity-0 pointer-events-none"}
        `}
      >
        <Button
          onClick={(e) => {
            e.stopPropagation();
            onAction();
          }}
          disabled={isSubmitting || !showAction}
        >
          {isSubmitting && pathType === "quick" ? <Spinner /> : option.actionLabel}
        </Button>
      </div>
    </div>
  );
};

export default function PathSelectionStep({
  data,
  updateData,
  onNext,
}: StepComponentProps) {
  const { setupPath } = data as { setupPath?: PathType };
  const [selectedPath, setSelectedPath] = useState<PathType>(setupPath ?? "quick");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!setupPath) {
      updateData({ setupPath: "quick" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePathSelect = (path: PathType) => {
    if (isSubmitting) return;
    setSelectedPath(path);
    setSubmitError(null);
    updateData({ setupPath: path });
  };

  const handleAction = async (path: PathType) => {
    if (path === "advanced") {
      onNext();
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    const { error } = await submitInitConfig(data as Record<string, unknown>);
    if (error) {
      setSubmitError(error);
      setIsSubmitting(false);
      return;
    }
    updateData({ showSuccess: true });
    setIsSubmitting(false);
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {(Object.keys(pathOptions) as PathType[]).map((pathType) => (
          <PathOptionCard
            key={pathType}
            pathType={pathType}
            isSelected={selectedPath === pathType}
            isSubmitting={isSubmitting}
            onSelect={() => handlePathSelect(pathType)}
            onAction={() => handleAction(pathType)}
          />
        ))}
      </div>

      <div className="mt-6 p-4">
        <h3 className="text-lg font-semibold text-solace-blue mb-3">
          What you&apos;ll get after setup:
        </h3>
        <ul className="space-y-2 text-gray-700">
          {commonOutcomes.map((outcome) => (
            <li key={outcome} className="flex items-center">
              <CheckIcon />
              {outcome}
            </li>
          ))}
        </ul>
      </div>

      {submitError && (
        <div className="p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
          <p className="font-medium">Error initializing project</p>
          <p>{submitError}</p>
        </div>
      )}
    </div>
  );
}
