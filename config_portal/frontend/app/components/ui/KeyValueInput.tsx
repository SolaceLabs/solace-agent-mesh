import React, { useState, KeyboardEvent } from "react";
import FormField from "./FormField";
import Input from "./Input";
import Button from "./Button";

interface KeyValueInputProps {
  id: string;
  label: string;
  values: Record<string, string>;
  onChange: (newValues: Record<string, string>) => void;
  placeholder?: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
}

const KeyValueInput: React.FC<KeyValueInputProps> = ({
  id,
  label,
  values,
  onChange,
  placeholder,
  helpText,
  error,
  required,
  keyPlaceholder = "Key",
  valuePlaceholder = "Value",
}) => {
  const [keyInput, setKeyInput] = useState("");
  const [valueInput, setValueInput] = useState("");

  const handleAddItem = () => {
    const trimmedKey = keyInput.trim();
    const trimmedValue = valueInput.trim();

    if (trimmedKey === "" || trimmedValue === "") {
      return;
    }

    // Avoid silently overwriting an existing key; existing entries
    // should be updated via the inline edit path instead.
    if (trimmedKey in values) {
      return;
    }

    onChange({ ...values, [trimmedKey]: trimmedValue });
    setKeyInput("");
    setValueInput("");
  };

  const handleRemoveItem = (keyToRemove: string) => {
    const newValues = { ...values };
    delete newValues[keyToRemove];
    onChange(newValues);
  };

  const handleUpdateValue = (key: string, newValue: string) => {
    onChange({ ...values, [key]: newValue });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddItem();
    }
  };

  const entries: [string, string][] = Object.entries(values);

  return (
    <FormField
      label={label}
      htmlFor={id}
      helpText={helpText}
      error={error}
      required={required}
    >
      <div className="space-y-2">
        {/* Input row for adding new key-value pairs */}
        <div className="flex items-center space-x-2">
          <Input
            id={`${id}-key`}
            name={`${id}-key`}
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={keyPlaceholder}
            className="flex-1"
          />
          <Input
            id={`${id}-value`}
            name={`${id}-value`}
            value={valueInput}
            onChange={(e) => setValueInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={valuePlaceholder}
            className="flex-1"
          />
          <Button onClick={handleAddItem} variant="secondary" type="button">
            Add
          </Button>
        </div>

        {/* Display existing key-value pairs */}
        {entries.length > 0 && (
          <div className="border border-gray-200 rounded-md divide-y divide-gray-200">
            {entries.map(([key, value]: [string, string]) => (
              <div
                key={key}
                className="flex items-center space-x-2 p-2 hover:bg-gray-50"
              >
                <div className="flex-1 font-mono text-sm text-gray-700 px-2 py-1 bg-gray-100 rounded">
                  {key}
                </div>
                <Input
                  id={`${id}-value-${key}`}
                  value={value}
                  onChange={(e) => handleUpdateValue(key, e.target.value)}
                  className="flex-1 text-sm"
                  placeholder="Value"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveItem(key)}
                  className="text-red-500 hover:text-red-700 focus:outline-none px-2"
                  aria-label={`Remove ${key}`}
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Placeholder when empty */}
        {entries.length === 0 && placeholder && (
          <div className="p-3 border border-dashed border-gray-300 rounded-md flex items-center justify-center">
            <p className="text-sm text-gray-400">{placeholder}</p>
          </div>
        )}
      </div>
    </FormField>
  );
};

export default KeyValueInput;
