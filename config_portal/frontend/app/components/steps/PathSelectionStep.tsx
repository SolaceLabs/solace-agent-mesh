import { useState } from 'react';
import Button from '../ui/Button';

type PathType = 'quick' | 'advanced';

type PathSelectionStepProps = {
  data: any;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

// Reusable check icon component
const CheckIcon = () => (
  <svg className="w-4 h-4 mr-1.5 text-green-500" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
  </svg>
);

// Path option configuration
const pathOptions: Record<PathType, {
  title: string;
  timeEstimate: string;
  timeColor: string;
  description: string;
  features: string[];
}> = {
  quick: {
    title: 'Get Started Quickly',
    timeEstimate: '2 minutes',
    timeColor: 'green',
    description: 'Simple setup with recommended defaults',
    features: [
      'Configure AI provider',
      'Uses sensible defaults for everything else'
    ]
  },
  advanced: {
    title: 'Advanced Setup',
    timeEstimate: '10 minutes',
    timeColor: 'blue',
    description: 'Full control over all configuration options',
    features: [
      'Configure project structure',
      'Configure broker settings',
      'Configure AI provider',
      'Configure built-in agents',
      'Configure file service'
    ]
  }
};

// Path option card component
const PathOptionCard = ({
  pathType,
  isSelected,
  onSelect
}: {
  pathType: PathType;
  isSelected: boolean;
  onSelect: () => void;
}) => {
  const option = pathOptions[pathType];
  
  return (
    <div
      className={`
        border rounded-lg p-6 cursor-pointer transition-all
        ${isSelected
          ? 'border-solace-blue bg-solace-light-blue/10 shadow-md'
          : 'border-gray-200 hover:border-solace-blue/50 hover:bg-gray-50'}
      `}
      onClick={onSelect}
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xl font-bold text-solace-blue">{option.title}</h3>
        <span className={`bg-${option.timeColor}-100 text-${option.timeColor}-800 text-xs font-medium px-2.5 py-0.5 rounded`}>
          {option.timeEstimate}
        </span>
      </div>
      <p className="text-gray-600 mb-4">{option.description}</p>
      <ul className="space-y-2 text-sm text-gray-600 mb-4">
        {option.features.map((feature, index) => (
          <li key={index} className="flex items-center">
            <CheckIcon />
            {feature}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default function PathSelectionStep({ data, updateData, onNext, onPrevious }: PathSelectionStepProps) {
  const [selectedPath, setSelectedPath] = useState<PathType | null>(
    data.setupPath || null
  );

  const handlePathSelect = (path: PathType) => {
    setSelectedPath(path);
    // Update the parent component with the selected path
    updateData({ setupPath: path });
  };

  const handleContinue = () => {
    if (selectedPath) {
      onNext();
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-solace-blue mb-2">Choose Your Setup Path</h2>
        <p className="text-gray-600">Select the setup option that best fits your needs</p>
      </div>

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

      <div className="mt-8 flex justify-end">
        <Button
          onClick={handleContinue}
          disabled={!selectedPath}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}