import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { ChatSidebar } from './ChatSidebar';
import { ChatMain } from './ChatMain';

export const ChatLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleNewConversation = () => {
    setActiveConversation('new');
  };

  const handleConversationCreated = (conversationId: string) => {
    // Switch to the new conversation
    setActiveConversation(conversationId);
    // Refresh the sidebar to show new conversation
    setRefreshTrigger(prev => prev + 1);
  };

  const handleManageConnections = () => {
    navigate('/connections');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <ChatSidebar 
        isOpen={sidebarOpen}
        user={user}
        activeConversation={activeConversation}
        onConversationSelect={setActiveConversation}
        onNewConversation={handleNewConversation}
        onManageConnections={handleManageConnections}
        onLogout={logout}
        refreshTrigger={refreshTrigger}
      />

      {/* Main Chat Area */}
      <ChatMain 
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        activeConversation={activeConversation}
        onNewConversation={handleNewConversation}
        onConversationCreated={handleConversationCreated}
        onManageConnections={handleManageConnections}
      />
    </div>
  );
};