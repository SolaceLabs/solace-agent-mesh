import SuccessScreen from './SuccessScreen';

type SuccessStepProps = {
  data: Record<string, any>;
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function SuccessStep({ data }: SuccessStepProps) {
  return <SuccessScreen />;
}