import React, { useState } from 'react';
import { Send, ChevronDown, Database } from 'lucide-react';
import { Connection } from '../../types/chat';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (message: string) => void;
  loading: boolean;
  connections: Connection[];
  selectedConnection: Connection | null;
  onConnectionSelect: (connection: Connection) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSend,
  loading,
  connections,
  selectedConnection,
  onConnectionSelect
}) => {
  const [showDropdown, setShowDropdown] = useState(false);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && selectedConnection && !loading) {
      e.preventDefault();
      onSend(value);
    }
  };

  const handleSend = () => {
    if (selectedConnection && !loading) {
      onSend(value);
    }
  };

  const trainedConnections = connections.filter(conn => conn.status === 'trained');
  const canSend = value.trim() && selectedConnection && !loading;

  return (
    <div className="max-w-3xl mx-auto px-4">
      {/* Input Container */}
      <div className="relative">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={selectedConnection ? "Message Tex2SQL..." : "Select a connection to start chatting"}
          disabled={!selectedConnection || loading}
          className={`w-full p-3 pr-12 border rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all min-h-[52px] max-h-[200px] ${
            !selectedConnection 
              ? 'bg-gray-50 border-gray-200 text-gray-400' 
              : 'bg-white border-gray-300 text-gray-900'
          }`}
          rows={1}
        />
        
        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={`absolute right-2 bottom-2 w-8 h-8 rounded-lg transition-all ${
            canSend
              ? 'bg-black text-white hover:bg-gray-800'
              : 'bg-gray-200 text-gray-400'
          }`}
        >
          <Send size={16} className="mx-auto" />
        </button>
      </div>

      {/* Bottom Row */}
      <div className="flex items-center justify-between mt-2 px-1">
        {/* Connection Selector */}
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            disabled={trainedConnections.length === 0}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs rounded-md transition-colors ${
              trainedConnections.length === 0
                ? 'text-gray-400 cursor-not-allowed'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Database size={12} />
            <span>
              {selectedConnection?.name || 'Select DB'}
            </span>
            {trainedConnections.length > 0 && (
              <ChevronDown size={12} />
            )}
          </button>

          {/* Dropdown */}
          {showDropdown && trainedConnections.length > 0 && (
            <div className="absolute bottom-full left-0 mb-2 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-[180px]">
              {trainedConnections.map(connection => (
                <button
                  key={connection.id}
                  onClick={() => {
                    onConnectionSelect(connection);
                    setShowDropdown(false);
                  }}
                  className={`w-full flex items-center gap-2 p-2 text-left hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg ${
                    selectedConnection?.id === connection.id ? 'bg-blue-50' : ''
                  }`}
                >
                  <Database size={12} className="text-green-600" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{connection.name}</div>
                    <div className="text-xs text-gray-500 truncate">{connection.server}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Helper Text */}
        <div className="text-xs text-gray-400">
          Tex2SQL can make mistakes
        </div>
      </div>

      {/* Click outside */}
      {showDropdown && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setShowDropdown(false)}
        />
      )}
    </div>
  );
};