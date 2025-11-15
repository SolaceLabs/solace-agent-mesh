import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/lib/components/ui';
import { MarkdownHTMLConverter } from '@/lib/components';
import { useChatContext } from '@/lib/hooks';
import type { MessageFE, TextPart } from '@/lib/types';

interface EditableMessageContentProps {
  message: MessageFE;
  isEditing: boolean;
  onCancelEdit: () => void;
  bubbleWidth?: number | null;
}

export const EditableMessageContent: React.FC<EditableMessageContentProps> = ({
  message,
  isEditing,
  onCancelEdit,
  bubbleWidth
}) => {
  const { addNotification, handleSubmit, messages, setMessages } = useChatContext();
  const [editedContent, setEditedContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Extract text content from message parts
  const getTextContent = (): string => {
    if (!message.parts || message.parts.length === 0) {
      return '';
    }
    const textParts = message.parts.filter(p => p.kind === "text") as TextPart[];
    return textParts.map(p => p.text).join("");
  };

  // Initialize edited content when entering edit mode
  useEffect(() => {
    if (isEditing) {
      const content = getTextContent();
      setEditedContent(content);
      
      // Focus and select all text after a brief delay
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          textareaRef.current.select();
        }
      }, 100);
    }
  }, [isEditing, getTextContent]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current && isEditing) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editedContent, isEditing]);

  const handleSave = async () => {
    if (!editedContent.trim()) {
      addNotification("Message content cannot be empty", "error");
      return;
    }

    setIsSaving(true);
    try {
      // Find the index of the current message
      const messageIndex = messages.findIndex(m => m.metadata?.messageId === message.metadata?.messageId);
      
      if (messageIndex !== -1) {
        // Remove all messages after and including this one
        // This will clear the old user message and any AI responses that followed
        const newMessages = messages.slice(0, messageIndex);
        setMessages(newMessages);
      }
      
      // Submit the edited message as a new message
      await handleSubmit(new Event('submit') as unknown as React.FormEvent, null, editedContent.trim());
      onCancelEdit();
      addNotification("Message updated and sent!", "success");
    } catch (error) {
      console.error('Failed to save message:', error);
      addNotification(`Failed to update message: ${error instanceof Error ? error.message : "Unknown error"}`, "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Save on Ctrl+Enter or Cmd+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
    // Cancel on Escape
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancelEdit();
    }
  };

  if (!isEditing) {
    // Render normal message content with ref to capture width
    const displayText = getTextContent().trim();
    return (
      <div ref={contentRef}>
        <MarkdownHTMLConverter>{displayText}</MarkdownHTMLConverter>
      </div>
    );
  }

  const editContainerStyle = bubbleWidth
    ? { width: `${bubbleWidth}px`, minWidth: '300px' }
    : { minWidth: '300px' };
  
  return (
    <div className="space-y-2 p-4" style={editContainerStyle}>
      <textarea
        ref={textareaRef}
        value={editedContent}
        onChange={(e) => setEditedContent(e.target.value)}
        onKeyDown={handleKeyDown}
        className="w-full min-h-[60px] p-2 border border-blue-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-transparent dark:border-blue-600 dark:text-white font-sans text-sm bg-white"
        placeholder="Edit your message..."
        disabled={isSaving}
      />
      <div className="flex justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancelEdit}
          disabled={isSaving}
          className="h-8 px-3 text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
        >
          Cancel
        </Button>
        <Button
          variant="default"
          size="sm"
          onClick={handleSave}
          disabled={isSaving || !editedContent.trim()}
          className="h-8 px-3 text-sm"
        >
          {isSaving ? 'Saving...' : 'Save & Resubmit'}
        </Button>
      </div>
    </div>
  );
};