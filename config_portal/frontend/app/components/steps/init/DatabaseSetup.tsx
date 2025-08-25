import React from "react";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Button from "../../ui/Button";
import { InfoBox } from "../../ui/InfoBoxes";
import { StepComponentProps } from "../../InitializationFlow";

export default function DatabaseSetup({
  data,
  updateData,
  onNext,
  onPrevious,
}: StepComponentProps) {
  const { database_url } = data as { database_url?: string };

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
          A local SQLite database will be created for your project to store chat
          history and session data. You can override this by providing a
          connection string to a different database.
        </InfoBox>

        <FormField
          label="Database URL"
          htmlFor="database_url"
          helpText="Leave blank to use the default SQLite database."
        >
          <Input
            id="database_url"
            name="database_url"
            value={database_url || ""}
            onChange={handleChange}
            placeholder="e.g., sqlite:///database.db"
          />
        </FormField>
      </div>

      <div className="mt-8 flex justify-end space-x-4">
        <Button onClick={onPrevious} variant="outline">
          Previous
        </Button>
        <Button type="submit">
          Next
        </Button>
      </div>
    </form>
  );
}