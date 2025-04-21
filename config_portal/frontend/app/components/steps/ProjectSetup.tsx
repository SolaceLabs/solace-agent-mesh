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

export default function ProjectSetup({ data, updateData, onNext, onPrevious }: Readonly<ProjectSetupProps>) {
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
          The namespace is a unique identifier that will be prefixed to all your event topics in the Solace Agent Mesh.
          Choose something meaningful to your organization or project.
        </InfoBox>
        
        <FormField 
          label="Project Namespace" 
          htmlFor="namespace"
          helpText="Any simple text identifier that makes sense for your project (e.g., 'my-project', 'acme-corp')"
          required
        >
          <Input
            id="namespace"
            name="namespace"
            value={data.namespace}
            onChange={handleChange}
            placeholder="Enter a namespace (e.g., my-project)"
            required
          />
        </FormField>
      </div>
      
      <div className="mt-8 flex justify-end space-x-4">
        <Button 
          onClick={onPrevious}
          variant="outline"
          disabled={true}  // if we want to allow going back then data needs to be cleared on every time path selection is altered
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