import { Step } from "./InitializationFlow";

type StepIndicatorProps = {
  steps: Step[];
  currentStepIndex: number;
  onStepClick?: (index: number) => void;
};

export default function StepIndicator({
  steps,
  currentStepIndex,
  onStepClick,
}: StepIndicatorProps) {
  return (
    <div className="relative w-full">
      <div className="absolute top-5 left-0 right-0 h-1 bg-gray-300 mr-9 ml-9">
        <div
          className="h-full bg-solace-green transition-all duration-300 ease-in-out"
          style={{
            width:
              currentStepIndex === 0
                ? "0%"
                : `${(currentStepIndex / (steps.length - 1)) * 100}%`,
          }}
        />
      </div>

      <div className="flex items-center justify-between w-full relative z-10">
        {steps.map((step, index) => {
          const isActive = index === currentStepIndex;
          const isCompleted = index < currentStepIndex;

          return (
            <div key={step.id} className="flex flex-col items-center">
              <button
                onClick={() => onStepClick?.(index)}
                disabled={!onStepClick}
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center
                  font-bold transition-colors duration-300
                  ${isActive ? "bg-solace-green text-white" : ""}
                  ${isCompleted ? "bg-solace-dark-green text-white" : ""}
                  ${
                    !isActive && !isCompleted ? "bg-gray-200 text-gray-600" : ""
                  }
                  ${onStepClick ? "cursor-pointer" : "cursor-default"}
                `}
              >
                {isCompleted ? (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  index + 1
                )}
              </button>

              <span
                className={`
                  mt-2 text-xs font-medium text-center
                  ${isActive ? "text-solace-green" : ""}
                  ${isCompleted ? "text-solace-dark-green" : ""}
                  ${!isActive && !isCompleted ? "text-gray-500" : ""}
                `}
              >
                {step.title}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
