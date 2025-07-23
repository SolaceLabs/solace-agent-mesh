import React, { useState, useEffect } from "react";
import { StepProps, Skill } from "../../AddAgentFlow";
import FormField from "../../ui/FormField";
import Input from "../../ui/Input";
import Checkbox from "../../ui/Checkbox";
import ChipInput from "../../ui/ChipInput";
import Button from "../../ui/Button";
import Modal from "../../ui/Modal";

const PencilIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-4 w-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
    />
  </svg>
);

const TrashIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-4 w-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
    />
  </svg>
);

const AgentCardStep: React.FC<StepProps> = ({
  data,
  updateData,
  onNext,
  onPrevious,
}) => {
  const [isSkillsModalOpen, setIsSkillsModalOpen] = useState(false);
  const [currentEditingSkill, setCurrentEditingSkill] = useState<Skill | null>(
    null
  );
  const [originalSkillIdForEdit, setOriginalSkillIdForEdit] = useState<
    string | null
  >(null);
  const [skillFormState, setSkillFormState] = useState<Partial<Skill>>({});
  const [skillFormError, setSkillFormError] = useState<string | null>(null);

  useEffect(() => {
    if (isSkillsModalOpen) {
      if (currentEditingSkill) {
        setSkillFormState(currentEditingSkill);
        setOriginalSkillIdForEdit(currentEditingSkill.id);
      } else {
        setSkillFormState({});
        setOriginalSkillIdForEdit(null);
      }
      setSkillFormError(null);
    }
  }, [currentEditingSkill, isSkillsModalOpen]);

  const handleGenericChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = e.target;
    const val =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : value;
    updateData({ [name]: val });
  };

  const handleSkillFormChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setSkillFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSaveSkill = () => {
    if (
      !skillFormState.id ||
      skillFormState.id.trim() === "" ||
      !skillFormState.name ||
      skillFormState.name.trim() === "" ||
      !skillFormState.description ||
      skillFormState.description.trim() === ""
    ) {
      setSkillFormError(
        "Skill ID, Name, and Description are required and cannot be empty."
      );
      return;
    }
    setSkillFormError(null);

    const currentSkills = Array.isArray(data.agent_card_skills)
      ? [...data.agent_card_skills]
      : [];
    const formSkillId = skillFormState.id!;

    const conflictingSkillIndex = currentSkills.findIndex(
      (s) => s.id === formSkillId
    );

    if (currentEditingSkill) {
      if (
        originalSkillIdForEdit !== formSkillId &&
        conflictingSkillIndex !== -1
      ) {
        setSkillFormError(
          `Skill ID "${formSkillId}" already exists. Please use a unique ID.`
        );
        return;
      }
      const skillToUpdateIndex = currentSkills.findIndex(
        (s) => s.id === originalSkillIdForEdit
      );
      if (skillToUpdateIndex !== -1) {
        currentSkills[skillToUpdateIndex] = { ...skillFormState } as Skill;
      } else {
        setSkillFormError("Error finding the original skill to update.");
        return;
      }
    } else {
      if (conflictingSkillIndex !== -1) {
        setSkillFormError(
          `Skill ID "${formSkillId}" already exists. Please use a unique ID.`
        );
        return;
      }
      currentSkills.push({ ...skillFormState } as Skill);
    }

    updateData({ agent_card_skills: currentSkills });
    setIsSkillsModalOpen(false);
    setCurrentEditingSkill(null);
    setOriginalSkillIdForEdit(null);
  };

  const openModalForEdit = (skillToEdit: Skill) => {
    setCurrentEditingSkill(skillToEdit);
    setIsSkillsModalOpen(true);
  };

  const openModalForNew = () => {
    setCurrentEditingSkill(null);
    setIsSkillsModalOpen(true);
  };

  const handleDeleteSkill = (skillId: string) => {
    const currentSkills = Array.isArray(data.agent_card_skills)
      ? data.agent_card_skills
      : [];
    updateData({
      agent_card_skills: currentSkills.filter((s) => s.id !== skillId),
    });
  };

  const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateData({ [name]: value === "" ? undefined : Number(value) });
  };

  const defaultDesc = "A helpful assistant capable of complex tasks.";

  return (
    <div className="space-y-6">
      <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4">
        Agent Card & Discovery
      </h3>

      <FormField
        label="Agent Card Description"
        htmlFor="agent_card_description"
        helpText="A concise description of the agent's capabilities."
      >
        <textarea
          id="agent_card_description"
          name="agent_card_description"
          rows={3}
          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm"
          value={data.agent_card_description || defaultDesc}
          onChange={handleGenericChange}
          placeholder={defaultDesc}
        />
      </FormField>

      <ChipInput
        id="agent_card_default_input_modes"
        label="Default Input Modes"
        values={data.agent_card_default_input_modes || []}
        onChange={(newValues) =>
          updateData({ agent_card_default_input_modes: newValues })
        }
        helpText="Enter input modes (e.g., text, file) and press Add."
        placeholder="No input modes added yet."
        inputPlaceholder="e.g., text"
      />

      <ChipInput
        id="agent_card_default_output_modes"
        label="Default Output Modes"
        values={data.agent_card_default_output_modes || []}
        onChange={(newValues) =>
          updateData({ agent_card_default_output_modes: newValues })
        }
        helpText="Enter output modes (e.g., text, file) and press Add."
        placeholder="No output modes added yet."
        inputPlaceholder="e.g., file"
      />

      <FormField label="Skills" htmlFor="add_skill_button">
        <div className="mb-2">
          <Button type="button" variant="outline" onClick={openModalForNew}>
            Add New Skill
          </Button>
        </div>
        {data.agent_card_skills && data.agent_card_skills.length > 0 ? (
          <div className="overflow-x-auto border rounded-md">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-500 tracking-wider">
                    ID
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500 tracking-wider">
                    Name
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500 tracking-wider">
                    Description
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500 tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.agent_card_skills.map((skill) => (
                  <tr key={skill.id}>
                    <td className="px-3 py-2 whitespace-nowrap font-mono text-xs">
                      {skill.id}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {skill.name}
                    </td>
                    <td className="px-3 py-2 break-words max-w-xs">
                      {skill.description}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap space-x-2">
                      <Button
                        variant="secondary"
                        onClick={() => openModalForEdit(skill)}
                        aria-label="Edit skill"
                      >
                        <PencilIcon />
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => handleDeleteSkill(skill.id)}
                        className="text-red-600 hover:text-red-800"
                        aria-label="Delete skill"
                      >
                        <TrashIcon />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm mt-2">No skills defined yet.</p>
        )}
      </FormField>

      <h3 className="text-xl font-semibold text-gray-800 border-b pb-2 mb-4 mt-8">
        Discovery & Communication
      </h3>

      <FormField
        label="Agent Card Publishing Interval (seconds)"
        htmlFor="agent_card_publishing_interval"
        helpText="Set to 0 to disable periodic publishing."
      >
        <Input
          id="agent_card_publishing_interval"
          name="agent_card_publishing_interval"
          type="number"
          value={
            data.agent_card_publishing_interval === undefined
              ? "10"
              : String(data.agent_card_publishing_interval)
          }
          onChange={handleNumberChange}
          placeholder="10"
        />
      </FormField>

      <FormField label="" htmlFor="agent_discovery_enabled">
        <Checkbox
          id="agent_discovery_enabled"
          checked={
            data.agent_discovery_enabled === undefined
              ? false
              : !!data.agent_discovery_enabled
          }
          onChange={(checked) =>
            updateData({ agent_discovery_enabled: checked })
          }
          label="Enable Agent Discovery (allows this agent to find and delegate to peers)"
        />
      </FormField>

      <ChipInput
        id="inter_agent_communication_allow_list"
        label="Inter-Agent Allow List"
        values={data.inter_agent_communication_allow_list || []}
        onChange={(newValues) =>
          updateData({ inter_agent_communication_allow_list: newValues })
        }
        helpText="Agent name patterns to allow delegation to (e.g., *, SpecificAgent*)."
        placeholder="No allow list patterns added."
        inputPlaceholder="e.g., *"
      />

      <ChipInput
        id="inter_agent_communication_deny_list"
        label="Inter-Agent Deny List"
        values={data.inter_agent_communication_deny_list || []}
        onChange={(newValues) =>
          updateData({ inter_agent_communication_deny_list: newValues })
        }
        helpText="Agent name patterns to deny delegation to."
        placeholder="No deny list patterns added."
        inputPlaceholder="e.g., RiskyAgent*"
      />

      <FormField
        label="Inter-Agent Request Timeout (seconds)"
        htmlFor="inter_agent_communication_timeout"
      >
        <Input
          id="inter_agent_communication_timeout"
          name="inter_agent_communication_timeout"
          type="number"
          value={
            data.inter_agent_communication_timeout === undefined
              ? "30"
              : String(data.inter_agent_communication_timeout)
          }
          onChange={handleNumberChange}
          placeholder="30"
        />
      </FormField>

      {isSkillsModalOpen && (
        <Modal
          onClose={() => {
            setIsSkillsModalOpen(false);
            setCurrentEditingSkill(null);
            setOriginalSkillIdForEdit(null);
          }}
          title={currentEditingSkill ? "Edit Skill" : "Add New Skill"}
        >
          <div className="space-y-4">
            <FormField
              label="Skill ID (e.g., function_name)"
              htmlFor="skill_id"
              required
              helpText="Unique identifier for the skill."
            >
              <Input
                id="skill_id"
                name="id"
                value={skillFormState.id || ""}
                onChange={handleSkillFormChange}
                placeholder="e.g., getWeather"
                disabled={false}
              />
            </FormField>
            <FormField
              label="Skill Name (Display Name)"
              htmlFor="skill_name"
              required
            >
              <Input
                id="skill_name"
                name="name"
                value={skillFormState.name || ""}
                onChange={handleSkillFormChange}
                placeholder="e.g., Data Analysis"
              />
            </FormField>
            <FormField
              label="Skill Description"
              htmlFor="skill_description"
              required
            >
              <textarea
                id="skill_description"
                name="description"
                rows={3}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-solace-blue focus:border-solace-blue sm:text-sm"
                value={skillFormState.description || ""}
                onChange={handleSkillFormChange}
                placeholder="e.g., Can analyze CSV data and generate reports."
              />
            </FormField>
            {skillFormError && (
              <p className="text-sm text-red-600">{skillFormError}</p>
            )}
            <div className="flex justify-end space-x-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setIsSkillsModalOpen(false);
                  setCurrentEditingSkill(null);
                  setOriginalSkillIdForEdit(null);
                }}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleSaveSkill}>
                {currentEditingSkill ? "Update Skill" : "Add Skill"}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      <div className="flex justify-end space-x-3 mt-8">
        <button
          type="button"
          onClick={onPrevious}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue-dark"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          className="px-4 py-2 text-sm font-medium text-white bg-solace-blue rounded-md shadow-sm hover:bg-solace-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-solace-blue"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default AgentCardStep;
