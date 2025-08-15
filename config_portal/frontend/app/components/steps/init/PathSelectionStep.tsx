import { useState } from "react";
import Button from "../../ui/Button";
import { StepComponentProps } from "../../InitializationFlow";

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

const pathOptions: Record<
  PathType,
  {
    title: string;
    timeEstimate: string;
    timeColor: string;
    description: string;
    features: string[];
  }
> = {
  quick: {
    title: "Get Started Quickly",
    timeEstimate: "2 minutes",
    timeColor: "green",
    description: "Simple setup with recommended defaults",
    features: [
      "Connect AI provider",
      "Uses sensible defaults for everything else",
    ],
  },
  advanced: {
    title: "Advanced Setup",
    timeEstimate: "10 minutes",
    timeColor: "blue",
    description: "Full control over all configuration options",
    features: [
      "Set namespace for topic prefixes",
      "Specify broker settings",
      "Connect AI provider",
      "Configure main orchestrator",
      "Configure Web UI Gateway",
    ],
  },
};

const commonOutcomes = [
  "Ready-to-use Solace Agent Mesh with basic capabilities",
  "Chat interface for immediate testing",
  "Foundation for adding more agents later",
];

const PathOptionCard = ({
  pathType,
  isSelected,
  onSelect,
}: {
  pathType: PathType;
  isSelected: boolean;
  onSelect: () => void;
}) => {
  const option = pathOptions[pathType];
  return (
    <div
      role="button"
      tabIndex={0}
      className={`
        border rounded-lg p-6 cursor-pointer transition-all
        ${
          isSelected
            ? "border-solace-blue bg-solace-light-blue/10 shadow-md"
            : "border-gray-200 hover:border-solace-blue/50 hover:bg-gray-50"
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

      <div>
        <ul className="space-y-2 text-sm text-gray-600">
          {option.features.map((feature) => (
            <li key={feature} className="flex items-center">
              <CheckIcon />
              {feature}
            </li>
          ))}
        </ul>
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
  const [selectedPath, setSelectedPath] = useState<PathType | null>(
    setupPath ?? null
  );

  const handlePathSelect = (path: PathType) => {
    setSelectedPath(path);
    updateData({ setupPath: path });
  };

  const handleContinue = () => {
    if (selectedPath) {
      onNext();
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {(Object.keys(pathOptions) as PathType[]).map((pathType) => (
          <PathOptionCard
            key={pathType}
            pathType={pathType}
            isSelected={selectedPath === pathType}
            onSelect={() => handlePathSelect(pathType)}
          />
        ))}
      </div>

      <div className="mt-6 p-4 border rounded-lg">
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

      <div className="mt-8 flex justify-end">
        <Button onClick={handleContinue} disabled={!selectedPath}>
          Continue
        </Button>
      </div>
    </div>
  );
}
