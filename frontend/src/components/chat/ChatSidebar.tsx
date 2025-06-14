import React, { useState, useEffect } from 'react';
import { Plus, Settings, User, History, Database } from 'lucide-react';
import { User as UserType } from '../../types/auth';
import { Conversation } from '../../types/chat';
import { chatService } from '../../services/chat';

interface ChatSidebarProps {
  isOpen: boolean;
  user: UserType | null;
  activeConversation: string | null;
  onConversationSelect: (id: string) => void;
  onNewConversation: () => void;
  onManageConnections: () => void;
  onLogout: () => void;
  refreshTrigger?: number;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  isOpen,
  user,
  activeConversation,
  onConversationSelect,
  onNewConversation,
  onManageConnections,
  onLogout,
  refreshTrigger = 0
}) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConversations();
  }, [refreshTrigger]);

  const loadConversations = async () => {
    try {
      console.log('Loading sidebar conversations...');
      const conversationsData = await chatService.getConversations();
      console.log('Loaded conversations:', conversationsData);
      setConversations(conversationsData);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
    
    if (diffInHours < 1) return 'Just now';
    if (diffInHours < 24) return `${diffInHours}h ago`;
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) return `${diffInDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={`${isOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-gray-900 text-white flex flex-col overflow-hidden`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-semibold">Tex2SQL</h1>
          <button
            onClick={onNewConversation}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            title="New Conversation"
          >
            <Plus size={16} />
          </button>
        </div>
        
        {/* Quick Actions */}
        <div className="space-y-2">
          <button
            onClick={onManageConnections}
            className="w-full flex items-center gap-3 p-2 text-sm text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
          >
            <Database size={16} />
            <span>Manage Connections</span>
          </button>
        </div>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <div className="text-sm text-gray-300 mb-3 flex items-center gap-2">
            <History size={14} />
            Recent Conversations
          </div>
          {loading ? (
            <div className="text-center text-gray-400 text-sm">Loading...</div>
          ) : conversations.length > 0 ? (
            <div className="space-y-2">
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => onConversationSelect(conv.id)}
                  className={`p-3 rounded-lg cursor-pointer transition-colors ${
                    activeConversation === conv.id 
                      ? 'bg-gray-700' 
                      : 'hover:bg-gray-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-sm font-medium truncate">{conv.title}</div>
                    {conv.is_pinned && (
                      <div className="text-yellow-400 text-xs">📌</div>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 truncate mt-1">
                    {conv.latest_message || `${conv.message_count} messages`}
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <div className="text-xs text-gray-500">
                      {formatTimeAgo(conv.last_message_at)}
                    </div>
                    <div className="text-xs text-gray-500">
                      {conv.connection_name}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-400 text-sm">
              No conversations yet
            </div>
          )}
        </div>
      </div>

      {/* User Menu */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center gap-3 p-2 hover:bg-gray-800 rounded-lg cursor-pointer group">
          <User size={16} />
          <div className="flex-1">
            <div className="text-sm font-medium">{user?.full_name || user?.username}</div>
            <div className="text-xs text-gray-400">{user?.email}</div>
          </div>
          <button
            onClick={onLogout}
            className="opacity-0 group-hover:opacity-100 transition-opacity"
            title="Logout"
          >
            <Settings size={16} className="text-gray-400 hover:text-red-400" />
          </button>
        </div>
      </div>
    </div>
  );
};