
import React, { useState, useEffect, useCallback } from 'react';
import Button from '../../ui/Button';
import { StatusBox } from '../../ui/InfoBoxes';
import Input from '../../ui/Input';
import LoadingSpinner from '../../ui/LoadingSpinner';
import FormField from '../../ui/FormField';
import Checkbox from '../../ui/Checkbox';
import { FaTrashAlt, FaPlus, FaChevronRight } from 'react-icons/fa';
import {
    AgentConfig,
    ConfigParam,
    AgentConfigurationResponse,
    UpdateAgentConfigurationResponse,
    SchemaDefinition,
} from '../types';

const getInputType = (schemaType?: string): 'number' | 'text' | 'checkbox' => {
    if (schemaType === 'boolean') return 'checkbox';
    if (schemaType === 'number') return 'number';
    return 'text';
};
const deepSet = (obj: any, path: (string | number)[], value: any): any => {
    if (!path || path.length === 0) { return value; }
    const currentKey = path[0];
    const remainingPath = path.slice(1);
    let newLevel: any;
    if (obj === null || typeof obj !== 'object') { newLevel = typeof currentKey === 'number' ? [] : {}; }
    else { newLevel = Array.isArray(obj) ? [...obj] : { ...obj }; }
    if (typeof currentKey === 'number' && Array.isArray(newLevel) && currentKey === newLevel.length) { newLevel.push(deepSet(undefined, remainingPath, value)); }
    else if (newLevel[currentKey] === undefined && remainingPath.length > 0) { const nextLevelBase = typeof remainingPath[0] === 'number' ? [] : {}; newLevel[currentKey] = deepSet(nextLevelBase, remainingPath, value); }
    else { newLevel[currentKey] = deepSet(newLevel[currentKey], remainingPath, value); }
    return newLevel;
};

const deepDelete = (obj: any, path: (string | number)[]): any => {
    if (!obj || typeof obj !== 'object' || !path || path.length === 0) { return obj; }
    const currentKey = path[0];
    const remainingPath = path.slice(1);
    if (remainingPath.length === 0) {
        if (Array.isArray(obj) && typeof currentKey === 'number') { if (currentKey >= 0 && currentKey < obj.length) { const newArray = [...obj]; newArray.splice(currentKey, 1); return newArray; } }
        else if (!Array.isArray(obj) && typeof currentKey === 'string') { if (obj.hasOwnProperty(currentKey)) { const newObj = { ...obj }; delete newObj[currentKey]; return newObj; } }
        return obj;
    }
    if (obj[currentKey] === undefined || obj[currentKey] === null) { return obj; }
    let newLevel = Array.isArray(obj) ? [...obj] : { ...obj };
    newLevel[currentKey] = deepDelete(newLevel[currentKey], remainingPath);
    return newLevel;
};

function transformDataWithSchemaOrder(data: any, schema: SchemaDefinition | null | undefined): any {
    if (!schema || data === null || data === undefined) {
        return data;
    }

    if (schema.type !== 'list' && schema.type !== 'dict') {
        return data;
    }

    // Handle Lists
    if (schema.type === 'list') {
        if (!Array.isArray(data)) {
            console.warn("Schema expected list, but data is not an array:", data, "at schema:", schema);
            return data;
        }
        // Recursively transform each item in the array
        return data.map(item => transformDataWithSchemaOrder(item, schema.item_schema));
    }

    // Handle Dictionaries (Objects)
    if (schema.type === 'dict') {
        if (typeof data !== 'object' || Array.isArray(data)) {
             console.warn("Schema expected dict, but data is not an object:", data, "at schema:", schema);
            return data;
        }

        const orderedData: Record<string, any> = {};
        const propertiesSchema = schema.properties;

        // Determine the keys to iterate over, prioritizing schema.key_order
        const keysToIterate = schema.key_order ?? Object.keys(data);

        for (const key of keysToIterate) {
            // Ensure the key actually exists in the original data before processing
            if (data.hasOwnProperty(key)) {
                const value = data[key];
                const propertySchema = propertiesSchema?.[key];
                // Recursively transform the value associated with the key
                orderedData[key] = transformDataWithSchemaOrder(value, propertySchema);
            } else {
                console.warn(`Key "${key}" from schema's key_order not found in data object. Skipping.`);
            }
        }    return orderedData;
    }

    return data;
}


//Collapsible Section Helper Component
const CollapsibleSection: React.FC<{ title: string; initialOpen?: boolean; children: React.ReactNode; level?: number }> = ({ title, initialOpen = false, children, level = 0 }) => {
    const indentClass = `ml-${Math.min(level * 2, 8)}`;
    return (
        <details open={initialOpen} className={`bg-gray-50/50 border rounded group ${indentClass} mb-2 shadow-sm overflow-hidden`}>
            <summary className="flex justify-between items-center p-2 cursor-pointer hover:bg-gray-100 list-none">
                <span className="font-semibold text-sm text-gray-700 truncate pr-2">{title}</span>
                <FaChevronRight className="text-gray-500 transition-transform duration-200 group-open:rotate-90 flex-shrink-0" />
            </summary>
            <div className="p-3 border-t bg-white"> {children} </div>
        </details>
    );
};

type AgentConfigureStepProps = {
    selectedAgent: AgentConfig | null;
    agentName: string;
    onInstallMore: () => void;
    onExit: () => void;
    onPrevious?: () => void;
};

export default function AgentConfigureStep({
    selectedAgent,
    agentName,
    onInstallMore,
    onExit,
}: Readonly<AgentConfigureStepProps>) {
    const [configParams, setConfigParams] = useState<ConfigParam[] | null>(null);
    const [formData, setFormData] = useState<Record<string, any>>({});
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [fetchError, setFetchError] = useState<string | null>(null);
    const [isSaving, setIsSaving] = useState<boolean>(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

    // fetch Configuration & Initial Data Transformation
    useEffect(() => {
        const fetchConfig = async () => {
            setIsLoading(true);
            setFetchError(null);
            setConfigParams(null);
            setFormData({});

            try {
                const response = await fetch(`/wizard_api/agents/configure/${encodeURIComponent(agentName)}`);
                if (!response.ok) {
                    let errorMsg = `Failed to fetch configuration (status ${response.status})`;
                    throw new Error(errorMsg);
                }
                const data: AgentConfigurationResponse = await response.json();
                if (data.status === 'error') { throw new Error(data.message || 'Failed to fetch configuration (API error)'); }

                if (data.config_params) {
                    console.log("Received config params (raw from backend):", JSON.stringify(data.config_params, null, 2));
                    setConfigParams(data.config_params); // Store original params with schema

                    // 1. Create initial form data structure (values only, potentially unordered objects)
                    const initialUnorderedFormData: Record<string, any> = {};
                    data.config_params.forEach(param => {
                        if (param.editable) {
                            if (param.type === 'simple') {
                                initialUnorderedFormData[param.name] = {
                                    value: param.current_value_str,
                                    use_env: param.is_env_var,
                                    original_env_str: param.is_env_var ? param.current_value_str : null,
                                };
                            } else if (param.type === 'list') {
                                initialUnorderedFormData[param.name] = structuredClone(param.values ?? []); // Ensure array even if null/undefined
                            } else if (param.type === 'dict') {
                                initialUnorderedFormData[param.name] = structuredClone(param.value ?? {}); // Ensure object even if null/undefined
                            }
                        }
                    });

                    // 2. Transform the data using the schema order
                    const orderedInitialFormData: Record<string, any> = {};
                    data.config_params.forEach(param => {
                        if (param.editable && initialUnorderedFormData.hasOwnProperty(param.name)) {
                            // Apply transformation to all types to handle nested structures correctly
                            console.log(`Transforming param: ${param.name} using schema:`, param.schema);
                            orderedInitialFormData[param.name] = transformDataWithSchemaOrder(
                                initialUnorderedFormData[param.name],
                                param.schema
                            );
                        }
                    });

                    console.log("Setting pre-ordered form data:", JSON.stringify(orderedInitialFormData, null, 2));
                    // 3. Set the state with the ORDERED data
                    setFormData(orderedInitialFormData);

                } else {
                    setConfigParams([]);
                }
            } catch (error: any) {
                 console.error("Error fetching agent configuration:", error);
                 setFetchError(error.message || 'An unknown error occurred.');
            } finally {
                setIsLoading(false);
            }
        };
        if (agentName) { fetchConfig(); }
        else { setIsLoading(false); setFetchError("Agent name is missing."); }
    }, [agentName]);


    const updateFormData = useCallback((path: (string | number)[], value: any) => {
        setFormData(prevData => deepSet(prevData, path, value));
        setSaveSuccess(false); setSaveError(null);
    }, []);

    const deleteFromFormData = useCallback((path: (string | number)[]) => {
        setFormData(prevData => deepDelete(prevData, path));
        setSaveSuccess(false); setSaveError(null);
    }, []);

    const handleSimpleValueChange = useCallback((paramName: string, newValue: string | boolean) => {
        updateFormData([paramName, 'value'], newValue);
    }, [updateFormData]);

    const handleEnvToggleChange = useCallback((paramName: string, useEnv: boolean) => {
        setFormData(prevData => {
            const currentSimpleParam = prevData[paramName];
            if (!currentSimpleParam || typeof currentSimpleParam !== 'object' || currentSimpleParam === null) { console.error("Cannot toggle env var on invalid simple param state:", paramName); return prevData; }
            let newValue = currentSimpleParam.value;
            if (useEnv && currentSimpleParam.original_env_str) { newValue = currentSimpleParam.original_env_str; }
            return deepSet(prevData, [paramName], { ...currentSimpleParam, use_env: useEnv, value: newValue });
        });
        setSaveSuccess(false); setSaveError(null);
    }, []);

    const handleValueChange = useCallback((path: (string | number)[], newValue: any) => {
        updateFormData(path, newValue);
    }, [updateFormData]);

    const handleAddListItem = useCallback((listPath: (string | number)[], itemSchema: SchemaDefinition | null | undefined) => {
        // Function to safely access nested properties
        const getNested = (obj: any, pathArr: (string | number)[]) => {
            try {
                return pathArr.reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
            } catch {
                return undefined;
            }
        };

        const currentList = getNested(formData, listPath);
        const newIndex = Array.isArray(currentList) ? currentList.length : 0;
        let newItem: any = null;

        if (itemSchema) {
            switch (itemSchema.type) {
                case 'dict':
                    newItem = {};
                    //Use key_order to create properties in the correct order
                    const keysToCreate = itemSchema.key_order ?? (itemSchema.properties ? Object.keys(itemSchema.properties) : []);
                    keysToCreate.forEach(key => {
                        const fieldSchema = itemSchema.properties?.[key];
                        // Assign default values based on field schema type
                        if (fieldSchema?.type === 'list') newItem[key] = [];
                        else if (fieldSchema?.type === 'dict') newItem[key] = {};
                        else if (fieldSchema?.type === 'boolean') newItem[key] = false;
                        else if (fieldSchema?.type === 'number') newItem[key] = 0;
                        else newItem[key] = '';
                    });
                    break;
                case 'list': newItem = []; break;
                case 'boolean': newItem = false; break;
                case 'number': newItem = 0; break;
                case 'string': default: newItem = ''; break;
            }
        } else {
            newItem = '';
        }
        updateFormData([...listPath, newIndex], newItem);
    }, [formData, updateFormData]); // Added dependencies

    const handleRemoveListItem = useCallback((itemPath: (string | number)[]) => {
        deleteFromFormData(itemPath);
    }, [deleteFromFormData]);


    // Save Configuration
    const handleSaveConfiguration = async () => {
        setIsSaving(true); setSaveError(null); setSaveSuccess(false);
        const payload: Record<string, any> = {};
        const currentConfigParams = configParams;

        if (!currentConfigParams) {
            setSaveError("Configuration parameters not loaded."); setIsSaving(false); return;
        }

        // Iterate through the original config parameters to decide what to include in payload
        currentConfigParams.forEach(param => {
            // Only include editable parameters that exist in the current form state
            if (param.editable && formData.hasOwnProperty(param.name)) {
                const formValue = formData[param.name];

                if (param.type === 'simple') {
                    // Check structure and send the raw value (literal or env placeholder)
                    if (formValue && typeof formValue === 'object' && 'value' in formValue) {
                         payload[param.name] = formValue.value;
                    } else {
                        console.warn(`Skipping simple param ${param.name} due to unexpected formData structure.`);
                    }
                } else {
                    // For lists and dicts, send the (ordered) structure from formData
                    payload[param.name] = structuredClone(formValue);
                }
            }
        });

        console.log("Saving payload:", JSON.stringify(payload, null, 2));
        try {
            const response = await fetch(`/wizard_api/agents/configure/${encodeURIComponent(agentName)}`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify(payload),
            });
            if (!response.ok) {
                let errorMsg = `Failed to save configuration (status ${response.status})`;
                try { const errorData = await response.json(); errorMsg = errorData.message || errorMsg; } catch (e) {/* Ignore */}
                throw new Error(errorMsg);
            }
            const data: UpdateAgentConfigurationResponse = await response.json();
            if (data.status === 'error') { throw new Error(data.message || 'Failed to save configuration (API error)'); }
            setSaveSuccess(true);
        } catch (error: any) {
            console.error("Error saving agent configuration:", error);
            setSaveError(error.message || 'An unknown error occurred while saving configuration.');
        } finally {
            setIsSaving(false);
        }
     };


    const renderEditableValue = useCallback((
        value: any,
        path: (string | number)[],
        schemaForValue: SchemaDefinition | null | undefined,
        nestingLevel: number = 0
    ): JSX.Element | null => {
        const currentKey = path[path.length - 1];
        const idPrefix = path.join('-');
        const indentClass = nestingLevel > 0 ? `ml-${Math.min(nestingLevel * 2, 8)}` : '';

        // 1. Handle Lists (Iterate over the ordered list 'value')
        if (Array.isArray(value)) {
            const itemSchema = schemaForValue?.item_schema;
            const listLabel = typeof currentKey === 'string' ? currentKey : `List @ ${path.slice(0,-1).join('.') || 'root'}`;
            return (
                <div className={`space-y-2 bg-gray-50/70 p-3 border rounded ${indentClass}`}>
                    <label className="block font-semibold text-sm text-gray-600 mb-2 capitalize">{listLabel.toString().replace(/_/g, ' ')}</label>
                    {value.length === 0 && <p className="text-sm text-gray-500 italic ml-2">List is empty.</p>}
                    {value.map((item, index) => {
                        const itemPath = [...path, index];
                        let itemTitle = `Item ${index + 1}`;
                        if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
                            const keys = Object.keys(item);
                            if (keys.length > 0) {
                                const firstKey = keys[0];
                                const firstValue = item[firstKey];
                                if ((typeof firstValue === 'string' && firstValue) || typeof firstValue === 'number') {
                                    const displayValue = typeof firstValue === 'string'
                                        ? `${firstValue.substring(0, 30)}${firstValue.length > 30 ? '...' : ''}` : firstValue;
                                    itemTitle += `: ${displayValue}`;
                                }
                            }
                        } else if (typeof item === 'string' && item) {
                             itemTitle += `: "${item.substring(0, 30)}${item.length > 30 ? '...' : ''}"`;
                        }

                        return (
                            <CollapsibleSection key={itemPath.join('-')} title={itemTitle} level={nestingLevel} initialOpen={value.length < 5 || nestingLevel > 0}>
                                {renderEditableValue(item, itemPath, itemSchema, nestingLevel + 1)}
                                <div className="mt-2 pt-2 border-t flex justify-end">
                                     <Button onClick={() => handleRemoveListItem(itemPath)} variant="secondary" className="text-xs py-1 px-2"> <FaTrashAlt className="mr-1" /> Remove Item {index + 1} </Button>
                                </div>
                            </CollapsibleSection>
                        );
                    })}
                    <div className="pt-2 mt-2 border-t">
                         <Button onClick={() => handleAddListItem(path, itemSchema)} variant="secondary" className="text-sm py-1"> <FaPlus className="mr-1" /> Add {typeof listLabel === 'string' ? listLabel.replace(/s$/, '') : 'Item'} </Button>
                    </div>
                </div>
            );
        }
        // 2. Handle Objects / Dictionaries (Iterate using Object.keys on ordered 'value')
        else if (value !== null && typeof value === 'object') {
            const propertiesSchema = schemaForValue?.properties;
            const objectLabel = typeof currentKey === 'string' ? currentKey : `Item ${currentKey}`;
            const orderedKeys = Object.keys(value);

            return (
                 <div className={`space-y-3 ${indentClass}`}>
                     {nestingLevel === 0 && typeof currentKey === 'string' && (
                         <label className="block font-semibold text-base text-gray-700 mb-2 capitalize border-b pb-1">{objectLabel.replace(/_/g, ' ')}</label>
                     )}
                     {orderedKeys.length === 0 && <p className="text-sm text-gray-500 italic">Object is empty.</p>}
                     {orderedKeys.map((fieldKey) => {
                         const fieldValue = value[fieldKey];
                         const fieldPath = [...path, fieldKey];
                         const fieldId = fieldPath.join('-');
                         const fieldSchema = propertiesSchema?.[fieldKey];
                         const fieldInputType = getInputType(fieldSchema?.type);
                         const isNestedStructure = fieldSchema?.type === 'list' || fieldSchema?.type === 'dict';

                         return (
                             <div key={fieldKey}>
                                 {isNestedStructure ? (
                                     renderEditableValue(fieldValue, fieldPath, fieldSchema, nestingLevel + 1)
                                 ) : fieldInputType === 'checkbox' ? (
                                      <Checkbox id={fieldId} label={fieldKey.replace(/_/g, ' ')} checked={!!fieldValue} onChange={(e) => handleValueChange(fieldPath, e.target.checked)} className="py-1 capitalize"/>
                                  ) : (
                                     <FormField label={fieldKey.replace(/_/g, ' ')} htmlFor={fieldId}>
                                         <Input id={fieldId} type={fieldInputType} value={fieldValue ?? ''} onChange={(e) => handleValueChange( fieldPath, fieldInputType === 'number' ? parseFloat(e.target.value) || 0 : e.target.value )} className="w-full text-sm"/>
                                     </FormField>
                                 )}
                             </div>
                         );
                     })}
                 </div>
            );
        }
        // 3. Handle Simple Primitives
        else {
            const inputType = schemaForValue?.type === 'number' ? 'number' : schemaForValue?.type === 'boolean' ? 'checkbox' : 'text';
            const fieldId = path.join('-');
            if (inputType === 'checkbox') {
                 return <Checkbox id={fieldId} label={`Value at ${path.join('.')}`} checked={!!value} onChange={(e) => handleValueChange(path, e.target.checked)} className="py-1"/>;
            } else {
                 return <Input id={fieldId} type={inputType} value={value ?? ''} onChange={(e) => handleValueChange( path, inputType === 'number' ? parseFloat(e.target.value) || 0 : e.target.value )} className="w-full text-sm" aria-label={`Value at path ${path.join('.')}`}/>;
             }
        }
    }, [formData, handleAddListItem, handleRemoveListItem, handleValueChange]);

    return (
        <div className="space-y-6 pb-20"> {/* Padding-bottom for sticky save bar */}
             {/* Status Box and Header */}
             <StatusBox variant='success'> Agent instance '<strong>{agentName}</strong>' (based on '{selectedAgent?.name}') was installed successfully! </StatusBox>
             <h3 className="text-lg font-semibold text-gray-800 border-b pb-2">Configure Agent: {agentName}</h3>

             {/* Loading / Error States */}
             {isLoading && <div className="flex justify-center p-6"><LoadingSpinner /> <span className="ml-2">Loading...</span></div>}
             {fetchError && <StatusBox variant='error'>{fetchError}</StatusBox>}

            {/* Configuration Form Area */}
            {!isLoading && !fetchError && configParams !== null && (
                 <div className='space-y-5'>
                     {configParams.length > 0 ? (
                         configParams.map(param => {

                            const currentValue = formData[param.name];
                            const paramSchema = param.schema;

                            return (
                                <div key={param.name} className="p-4 border rounded bg-white shadow-sm">
                                    {param.type === 'simple' ? (
                                        (() => {
                                            const formEntry = currentValue;
                                            if (!formEntry || typeof formEntry !== 'object') return <div className='text-red-500'>Error: Invalid state for {param.name}</div>;

                                            const sensitiveNames = ['key', 'password', 'secret', 'token'];
                                            const isSensitive = sensitiveNames.some(term => param.name.toLowerCase().includes(term));
                                            const inputType = getInputType(paramSchema?.type);

                                            return (
                                                <FormField label={param.name.replace(/_/g, ' ')} htmlFor={`param-${param.name}`}>
                                                    {param.is_env_var && (
                                                        <Checkbox
                                                            id={`${param.name}-env-toggle`}
                                                            label={`Use Environment Variable ${formEntry.use_env && `(${param.env_var_name ? `\${${param.env_var_name}${param.env_var_default ? `, ${param.env_var_default}` : ''}}` : 'Yes'})`}`}
                                                            checked={formEntry.use_env ?? false}
                                                            onChange={(e) => handleEnvToggleChange(param.name, e.target.checked)} />
                                                    )}
                                                    {!formEntry.use_env && param.is_env_var && isSensitive && ( <p className="text-xs text-orange-600 italic">Storing sensitive values directly is less secure.</p> )}

                                                    {/* Use handleSimpleValueChange for both input and checkbox */}
                                                    {inputType === 'checkbox' ? (
                                                         <Checkbox
                                                            id={`param-${param.name}-input`}
                                                            checked={!!formEntry.value}
                                                            onChange={(e) => handleSimpleValueChange(param.name, e.target.checked)}
                                                            disabled={formEntry.use_env ?? false}
                                                            className={` ${formEntry.use_env ? 'opacity-50' : ''}`} />
                                                    ) : (
                                                        <Input
                                                            id={`param-${param.name}-input`}
                                                            type={inputType} // text or number
                                                            value={formEntry.value ?? ''}
                                                            onChange={(e) => handleSimpleValueChange(param.name, e.target.value)}
                                                            disabled={formEntry.use_env ?? false}
                                                            className={`w-full ${formEntry.use_env ? 'bg-gray-100 cursor-not-allowed' : ''}`} />
                                                    )}
                                                </FormField>
                                            );
                                        })()
                                    ) : (
                                        renderEditableValue(currentValue, [param.name], paramSchema, 0)
                                    )}
                                </div>
                            );
                         })
                     ) : ( <p className="text-center italic text-gray-500">No editable configuration parameters found.</p> )}

                     {/* Save Button Area - Sticky Footer */}
                     {configParams.some(p => p.editable) && (
                         <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-sm py-3 px-4 border-t shadow-lg flex justify-end items-center space-x-3 z-50">
                             {saveError && <StatusBox variant='error' className="text-sm">{saveError}</StatusBox>}
                             {saveSuccess && <StatusBox variant='success' className="text-sm">Saved!</StatusBox>}
                             <Button onClick={handleSaveConfiguration} variant="primary" disabled={isSaving || isLoading} className={isSaving ? "opacity-70" : ""}> {isSaving ? "Saving..." : "Save Configuration"} </Button>
                         </div>
                    )}
                 </div>
             )}

             {/* Bottom Navigation */}
             <div className="flex justify-center space-x-4 pt-6">
                 <Button onClick={onInstallMore} variant="outline" disabled={isSaving}> Install Another Agent </Button>
                 <Button onClick={onExit} variant="secondary" disabled={isSaving}> Finish & Close </Button>
             </div>
        </div>
    );
}

