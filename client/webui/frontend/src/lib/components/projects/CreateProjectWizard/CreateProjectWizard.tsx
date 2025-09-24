import React from "react";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { Header } from "@/lib/components/header";
import { StepIndicator } from "./StepIndicator";
import { ProjectDetailsStep } from "./steps/ProjectDetailsStep";
import { FilesArtifactsStep } from "./steps/FilesArtifactsStep";
import { ReviewCreateStep } from "./steps/ReviewCreateStep";
import { useCreateProjectWizard } from "./hooks/useCreateProjectWizard";
import type { ProjectFormData } from "@/lib/types/projects";

interface CreateProjectWizardProps {
    onComplete: () => void;
    onCancel: () => void;
    onSubmit: (data: ProjectFormData) => Promise<void>;
}

const steps = [
    {
        title: "Project Details",
        description: "Basic information about your project",
        completed: false,
    },
    {
        title: "Files & Artifacts",
        description: "Upload project files and documents",
        completed: false,
    },
    {
        title: "Review & Create",
        description: "Review and finalize your project",
        completed: false,
    },
];

export const CreateProjectWizard: React.FC<CreateProjectWizardProps> = ({ onComplete, onCancel, onSubmit }) => {
    const {
        currentStep,
        formData,
        isSubmitting,
        isStepValid,
        goToStep,
        goToNextStep,
        goToPreviousStep,
        updateFormData,
        validateCurrentStep,
        submitProject,
    } = useCreateProjectWizard();

    const handleSubmit = async () => {
        await submitProject(async (data) => {
            await onSubmit(data);
            onComplete();
        });
    };

    const currentStepData = steps.map((step, index) => ({
        ...step,
        completed: index + 1 < currentStep || (index + 1 === currentStep && isStepValid(index + 1)),
    }));

    const renderCurrentStep = () => {
        const commonProps = {
            data: formData,
            onDataChange: updateFormData,
            onNext: goToNextStep,
            onPrevious: goToPreviousStep,
            onCancel,
            isValid: validateCurrentStep(),
            isSubmitting,
        };

        switch (currentStep) {
            case 1:
                return <ProjectDetailsStep {...commonProps} />;
            case 2:
                return <FilesArtifactsStep {...commonProps} />;
            case 3:
                return <ReviewCreateStep {...commonProps} onSubmit={handleSubmit} goToStep={goToStep} />;
            default:
                return null;
        }
    };

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Create New Project"
                buttons={[
                    <Button key="back" variant="ghost" onClick={onCancel} className="flex items-center gap-2">
                        <ArrowLeft className="h-4 w-4" />
                        Back to Projects
                    </Button>,
                ]}
            />
            <div className="flex-1 py-6 px-8">
                <div className="max-w-4xl mx-auto">
                    <StepIndicator currentStep={currentStep} totalSteps={3} steps={currentStepData} />
                    <div className="mt-8">{renderCurrentStep()}</div>
                </div>
            </div>
        </div>
    );
};
