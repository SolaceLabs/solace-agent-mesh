import React, { useState, useEffect, useCallback } from 'react';
import Input from './Input';

interface EnvVarOrLiteralInputProps {
    id: string;
    label: string;
    envVarString: string; 
    initialValue: string;
    dataType?: 'text' | 'number';
    showSecureWarning?: boolean;
    onChange: (value: string) => void;
    className?: string;
}

export default function EnvVarOrLiteralInput({
    id,
    label,
    envVarString,
    initialValue,
    dataType = 'text',
    showSecureWarning = false,
    onChange,
    className = '',
}: Readonly<EnvVarOrLiteralInputProps>) {

    const [source, setSource] = useState<'env' | 'literal'>('env');
    const [literalValue, setLiteralValue] = useState<string>('');

    // Effect to ensure parent knows the correct initial value on mount
    useEffect(() => {
        onChange(envVarString);
    }, []);

    const handleSourceChange = useCallback((newSource: 'env' | 'literal') => {
        setSource(newSource);
        onChange(newSource === 'env' ? envVarString : literalValue);
    }, [envVarString, literalValue, onChange]);

    const handleLiteralChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const newLiteral = event.target.value;
        setLiteralValue(newLiteral);
        if (source === 'literal') {
            onChange(newLiteral);
        }
    }, [source, onChange]);

    const envRadioId = `${id}-env`;
    const literalRadioId = `${id}-literal`;
    const literalInputId = `${id}-literal-input`;

    return (
        <div className={`p-3 border rounded bg-white ${className}`}>
            <label className="block font-medium text-gray-700 mb-2">{label}</label>

            <fieldset className="mb-3">
                <legend className="sr-only">Select source for {label}</legend>
                 <div className="flex items-center space-x-4 text-sm">
                    <div className="flex items-center">
                        <input id={envRadioId} name={`${id}-source`} type="radio" value="env" checked={source === 'env'} onChange={() => handleSourceChange('env')} className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"/>
                        <label htmlFor={envRadioId} className="ml-2 block text-gray-700 cursor-pointer"> Environment Variable </label>
                    </div>
                     <div className="flex items-center">
                        <input id={literalRadioId} name={`${id}-source`} type="radio" value="literal" checked={source === 'literal'} onChange={() => handleSourceChange('literal')} className="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"/>
                        <label htmlFor={literalRadioId} className="ml-2 block text-gray-700 cursor-pointer"> Literal Value </label>
                    </div>
                </div>
            </fieldset>

            {source === 'env' && (
                <div>
                     <label className="text-xs font-medium text-gray-500 block mb-1"> Using Environment Variable: </label>
                     <p className="text-sm p-2 bg-gray-100 rounded border border-gray-200 text-gray-700 font-mono break-all">
                         {envVarString || '(Not specified)'}
                     </p>
                </div>
            )}

            {source === 'literal' && (
                <div>
                     <label htmlFor={literalInputId} className="text-xs font-medium text-gray-500 block mb-1"> Enter Literal Value: </label>
                     <Input id={literalInputId} type={dataType} value={literalValue} onChange={handleLiteralChange} className="w-full"/>
                     {showSecureWarning && (
                        <p className="text-xs text-orange-600 mt-1 italic">
                            Note: Storing sensitive values directly here is less secure than using environment variables.
                        </p>
                     )}
                </div>
            )}
        </div>
    );
}