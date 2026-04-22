import { useEffect, useState } from "react";
import { Check, Sparkles } from "lucide-react";
import Button from "../../ui/Button";
import Spinner from "../../ui/Spinner";
import ErrorAlert from "../../ui/ErrorAlert";
import { StepComponentProps } from "../../InitializationFlow";
import { useInitSubmit } from "../../../common/useInitSubmit";

type PathType = "quick" | "advanced";

const CheckIcon = () => (
  <Check className="w-4 h-4 mr-1.5 text-green-500 flex-shrink-0" />
);

const SparkleIcon = () => (
  <Sparkles className="w-4 h-4 mr-1.5 text-solace-green flex-shrink-0" />
);

type PathOption = {
  title: string;
  timeEstimate: string;
  timeBadgeClass: string;
  description: string;
  features: string[];
  featureIcon: "check" | "sparkle";
  actionLabel: string;
};

const pathOptions: Record<PathType, PathOption> = {
  quick: {
    title: "Get Started Quickly",
    timeEstimate: "2 minutes",
    timeBadgeClass: "bg-green-100 text-green-800",
    description: "Automatically setup Solace Agent Mesh with sensible defaults.",
    features: [
      "Agents connected and ready to communicate",
      "AI task routing configured automatically",
      "Chat interface ready in your browser",
    ],
    featureIcon: "sparkle",
    actionLabel: "Initialize",
  },
  advanced: {
    title: "Advanced Setup",
    timeEstimate: "10 minutes",
    timeBadgeClass: "bg-blue-100 text-blue-800",
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
  "A working multi-agent AI system, ready to use",
  "Chat interface for immediate testing",
  "A foundation for adding more agents later",
];

const PathOptionCard = ({
  pathType,
  isSelected,
  isSubmitting,
  isLoading,
  onSelect,
  onAction,
}: {
  pathType: PathType;
  isSelected: boolean;
  isSubmitting: boolean;
  isLoading: boolean;
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
          className={`${option.timeBadgeClass} text-xs font-medium px-2.5 py-0.5 rounded`}
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
          disabled={isSubmitting || isLoading || !showAction}
        >
          {isSubmitting && pathType === "quick" ? (
            <div className="flex items-center space-x-2">
              <Spinner className="-ml-1 mr-2 text-white" />
              <span>Initializing...</span>
            </div>
          ) : (
            option.actionLabel
          )}
        </Button>
      </div>
    </div>
  );
};

export default function PathSelectionStep({
  data,
  updateData,
  onNext,
  isLoading = false,
}: StepComponentProps) {
  const { setupPath } = data as { setupPath?: PathType };
  const [selectedPath, setSelectedPath] = useState<PathType>(
    setupPath ?? "quick"
  );
  const { isSubmitting, submitError, submit, clearError } = useInitSubmit(
    data,
    updateData
  );

  useEffect(() => {
    if (!setupPath) {
      updateData({ setupPath: "quick" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePathSelect = (path: PathType) => {
    if (isSubmitting) return;
    setSelectedPath(path);
    clearError();
    updateData({ setupPath: path });
  };

  const handleAction = async (path: PathType) => {
    if (isLoading) return;
    if (path === "advanced") {
      onNext();
      return;
    }
    await submit();
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
            isLoading={isLoading}
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

      {submitError && <ErrorAlert message={submitError} />}
    </div>
  );
}
