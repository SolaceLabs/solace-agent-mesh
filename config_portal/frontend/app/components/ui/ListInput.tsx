import React, { useState, KeyboardEvent } from "react";
import FormField from "./FormField";
import Input from "./Input";
import Button from "./Button";

interface ListInputProps {
  id: string;
  label: string;
  values: string[];
  onChange: (newValues: string[]) => void;
  placeholder?: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  itemPlaceholder?: string;
}

const ListInput: React.FC<ListInputProps> = ({
  id,
  label,
  values,
  onChange,
  placeholder,
  helpText,
  error,
  required,
  itemPlaceholder = "Enter value",
}) => {
  const [inputValue, setInputValue] = useState<string>("");

  const handleAddItem = () => {
    if (inputValue.trim() === "") {
      return;
    }
    onChange([...values, inputValue.trim()]);
    setInputValue("");
  };

  const handleRemoveItem = (indexToRemove: number) => {
    onChange(values.filter((_, index) => index !== indexToRemove));
  };

  const handleUpdateItem = (index: number, newValue: string) => {
    const newValues = [...values];
    newValues[index] = newValue;
    onChange(newValues);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddItem();
    }
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    const newValues = [...values];
    [newValues[index - 1], newValues[index]] = [newValues[index], newValues[index - 1]];
    onChange(newValues);
  };

  const handleMoveDown = (index: number) => {
    if (index === values.length - 1) return;
    const newValues = [...values];
    [newValues[index], newValues[index + 1]] = [newValues[index + 1], newValues[index]];
    onChange(newValues);
  };

  return (
    <FormField
      label={label}
      htmlFor={id}
      helpText={helpText}
      error={error}
      required={required}
    >
      <div className="space-y-2">
        {/* Input row for adding new items */}
        <div className="flex items-center space-x-2">
          <Input
            id={id}
            name={id}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={itemPlaceholder}
            className="flex-1"
          />
          <Button onClick={handleAddItem} variant="secondary" type="button">
            Add
          </Button>
        </div>

        {/* Display existing items */}
        {values.length > 0 && (
          <div className="border border-gray-200 rounded-md divide-y divide-gray-200">
            {values.map((item: string, index: number) => (
              <div
                key={`${id}-${index}-${item}`}
                className="flex items-center space-x-2 p-2 hover:bg-gray-50"
              >
                <div className="flex flex-col space-y-1">
                  <button
                    type="button"
                    onClick={() => handleMoveUp(index)}
                    disabled={index === 0}
                    className={`text-xs ${
                      index === 0
                        ? "text-gray-300 cursor-not-allowed"
                        : "text-gray-500 hover:text-gray-700"
                    } focus:outline-none`}
                    aria-label="Move up"
                  >
                    ▲
                  </button>
                  <button
                    type="button"
                    onClick={() => handleMoveDown(index)}
                    disabled={index === values.length - 1}
                    className={`text-xs ${
                      index === values.length - 1
                        ? "text-gray-300 cursor-not-allowed"
                        : "text-gray-500 hover:text-gray-700"
                    } focus:outline-none`}
                    aria-label="Move down"
                  >
                    ▼
                  </button>
                </div>
                <span className="text-sm text-gray-500 w-6">{index}</span>
                <Input
                  id={`${id}-item-${index}`}
                  value={item}
                  onChange={(e) => handleUpdateItem(index, e.target.value)}
                  className="flex-1 text-sm"
                  placeholder={itemPlaceholder}
                />
                <button
                  type="button"
                  onClick={() => handleRemoveItem(index)}
                  className="text-red-500 hover:text-red-700 focus:outline-none px-2"
                  aria-label={`Remove item ${index}`}
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Placeholder when empty */}
        {values.length === 0 && placeholder && (
          <div className="p-3 border border-dashed border-gray-300 rounded-md flex items-center justify-center">
            <p className="text-sm text-gray-400">{placeholder}</p>
          </div>
        )}
      </div>
    </FormField>
  );
};

export default ListInput;
