import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Button from '../ui/Button';
import { InfoBox } from '../ui/InfoBoxes';

type ProjectSetupProps = {
  data: { namespace: string; [key: string]: any };
  updateData: (data: Record<string, any>) => void;
  onNext: () => void;
  onPrevious: () => void;
};

export default function ProjectSetup({ data, updateData, onNext, onPrevious }: ProjectSetupProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    updateData({ [e.target.name]: e.target.value });
  };
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNext();
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        <InfoBox className="mb-4">
          The namespace will be used as the topic prefix for all events in your Solace Agent Mesh.
        </InfoBox>
        
        <FormField 
          label="Project Namespace" 
          htmlFor="namespace"
          helpText="This will be used as the topic prefix for all events."
          required
        >
          <Input
            id="namespace"
            name="namespace"
            value={data.namespace}
            onChange={handleChange}
            placeholder="Enter a namespace for your project"
            required
          />
        </FormField>
      </div>
      
      <div className="mt-8 flex justify-end space-x-4">
        <Button 
          onClick={onPrevious}
          variant="outline"
        >
          Previous
        </Button>
        <Button 
          type="submit"
          disabled={!data.namespace?.trim()}
        >
          Next
        </Button>
      </div>
    </form>
  );
}