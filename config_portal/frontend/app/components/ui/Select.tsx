type SelectOption = {
  value: string;
  label: string;
};

type SelectProps = {
  id: string;
  options: SelectOption[];
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  name?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
};

export default function Select({
  id,
  options,
  value,
  onChange,
  name,
  required = false,
  disabled = false,
  className = '',
}: SelectProps) {
  return (
    <select
      id={id}
      name={name || id}
      value={value}
      onChange={onChange}
      required={required}
      disabled={disabled}
      className={`
        w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm 
        focus:outline-none focus:ring-blue-500 focus:border-blue-500 
        disabled:bg-gray-100 disabled:text-gray-500
        ${className}
      `}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}