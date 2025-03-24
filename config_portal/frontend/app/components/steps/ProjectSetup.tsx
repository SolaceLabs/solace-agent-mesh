import FormField from '../ui/FormField';
import Input from '../ui/Input';
import Button from '../ui/Button';

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
        <div className="p-4 bg-blue-50 rounded-md mb-4">
          <p className="text-sm text-blue-800">
            The namespace will be used as the topic prefix for all events in your Solace Agent Mesh.
          </p>
        </div>
        
        <FormField 
          label="Project Namespace" 
          htmlFor="namespace"
          helpText="This will be used as the topic prefix for all events."
          required
        >
          <Input
            id="namespace"
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
          disabled={true} // Disabled on first step
        >
          Previous
        </Button>
        <Button 
          onClick={onNext}
          disabled={!data.namespace.trim()}
        >
          Next
        </Button>
      </div>
    </form>
  );
}
