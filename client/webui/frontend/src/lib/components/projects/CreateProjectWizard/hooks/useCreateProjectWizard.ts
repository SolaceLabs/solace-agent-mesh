import { useState, useCallback } from "react";
import type { ProjectFormData } from "@/lib/types/projects";

interface WizardState {
    currentStep: number;
    formData: ProjectFormData;
    stepValidation: Record<number, boolean>;
    isSubmitting: boolean;
}

interface UseCreateProjectWizardReturn {
    currentStep: number;
    formData: ProjectFormData;
    isSubmitting: boolean;
    isStepValid: (step: number) => boolean;
    goToStep: (step: number) => void;
    goToNextStep: () => void;
    goToPreviousStep: () => void;
    updateFormData: (data: Partial<ProjectFormData>) => void;
    validateCurrentStep: () => boolean;
    submitProject: (onSubmit: (data: ProjectFormData) => Promise<void>) => Promise<void>;
}

const validateStep = (step: number, data: ProjectFormData): boolean => {
    switch (step) {
        case 1:
            // Project Details validation
            return !!(data.name && data.name.trim().length > 0);
        case 2:
            // Files validation (optional step, always valid)
            return true;
        case 3:
            // Review validation (check all previous steps)
            return !!(data.name && data.name.trim().length > 0);
        default:
            return false;
    }
};

export const useCreateProjectWizard = (): UseCreateProjectWizardReturn => {
    const [state, setState] = useState<WizardState>({
        currentStep: 1,
        formData: {
            name: "",
            description: "",
            system_prompt: "",
            files: null,
            fileDescriptions: {},
        },
        stepValidation: {},
        isSubmitting: false,
    });

    const isStepValid = useCallback((step: number): boolean => {
        return validateStep(step, state.formData);
    }, [state.formData]);

    const validateCurrentStep = useCallback((): boolean => {
        return isStepValid(state.currentStep);
    }, [isStepValid, state.currentStep]);

    const goToStep = useCallback((step: number) => {
        if (step >= 1 && step <= 3) {
            setState(prev => ({
                ...prev,
                currentStep: step,
            }));
        }
    }, []);

    const goToNextStep = useCallback(() => {
        if (validateCurrentStep() && state.currentStep < 3) {
            setState(prev => ({
                ...prev,
                currentStep: prev.currentStep + 1,
                stepValidation: {
                    ...prev.stepValidation,
                    [prev.currentStep]: true,
                },
            }));
        }
    }, [validateCurrentStep, state.currentStep]);

    const goToPreviousStep = useCallback(() => {
        if (state.currentStep > 1) {
            setState(prev => ({
                ...prev,
                currentStep: prev.currentStep - 1,
            }));
        }
    }, [state.currentStep]);

    const updateFormData = useCallback((data: Partial<ProjectFormData>) => {
        setState(prev => ({
            ...prev,
            formData: {
                ...prev.formData,
                ...data,
            },
        }));
    }, []);

    const submitProject = useCallback(async (onSubmit: (data: ProjectFormData) => Promise<void>) => {
        if (!isStepValid(3)) {
            return;
        }

        setState(prev => ({ ...prev, isSubmitting: true }));
        
        try {
            await onSubmit(state.formData);
        } finally {
            setState(prev => ({ ...prev, isSubmitting: false }));
        }
    }, [isStepValid, state.formData]);

    return {
        currentStep: state.currentStep,
        formData: state.formData,
        isSubmitting: state.isSubmitting,
        isStepValid,
        goToStep,
        goToNextStep,
        goToPreviousStep,
        updateFormData,
        validateCurrentStep,
        submitProject,
    };
};
