import { useState, useEffect } from "react";

type ToggleProps = {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
};

export default function Toggle({
  id,
  checked,
  onChange,
  disabled = false,
}: ToggleProps) {
  const [isChecked, setIsChecked] = useState(checked);

  useEffect(() => {
    setIsChecked(checked);
  }, [checked]);

  const handleChange = () => {
    if (!disabled) {
      const newState = !isChecked;
      setIsChecked(newState);
      onChange(newState);
    }
  };

  return (
    <div className="inline-block">
      <label
        htmlFor={id}
        className="relative inline-flex items-center cursor-pointer"
      >
        <input
          type="checkbox"
          id={id}
          name={id}
          checked={isChecked}
          onChange={handleChange}
          disabled={disabled}
          className="sr-only"
        />
        <div
          className={`
            relative w-11 h-6 rounded-full transition-colors duration-300 ease-in-out
            ${isChecked ? "bg-solace-green" : "bg-gray-300"}
            ${disabled ? "opacity-50" : ""}
          `}
        >
          <span
            className={`
              absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transform transition-transform duration-300 ease-in-out
              ${isChecked ? "translate-x-5" : "translate-x-0"}
            `}
          />
        </div>
        <span className="sr-only">{isChecked ? "Enabled" : "Disabled"}</span>
      </label>
    </div>
  );
}
