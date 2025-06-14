import React, { useState, useEffect } from 'react';
import { Menu } from 'lucide-react';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import { chatService } from '../../services/chat';
import { Connection } from '../../types/chat';

interface ChatMainProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  activeConversation: string | null;
  onNewConversation: () => void;
  onConversationCreated: (conversationId: string) => void;
  onManageConnections: () => void;
}

export const ChatMain: React.FC<ChatMainProps> = ({
  sidebarOpen,
  onToggleSidebar,
  activeConversation,
  onNewConversation,
  onConversationCreated,
  onManageConnections
}) => {
  const [messages, setMessages] = useState<any[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationData, setConversationData] = useState<any>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<Connection | null>(null);

  // Load connections on mount
  useEffect(() => {
    loadConnections();
  }, []);

  // Auto-select connection if only one trained connection exists
  useEffect(() => {
    const trainedConnections = connections.filter(conn => conn.status === 'trained');
    if (trainedConnections.length === 1 && !selectedConnection) {
      setSelectedConnection(trainedConnections[0]);
    } else if (trainedConnections.length === 0) {
      setSelectedConnection(null);
    }
  }, [connections, selectedConnection]);

  // Load conversation messages when activeConversation changes
  useEffect(() => {
    if (activeConversation && activeConversation !== 'new') {
      loadConversationMessages();
    } else {
      setMessages([]);
      setConversationData(null);
    }
  }, [activeConversation]);

  const loadConnections = async () => {
    try {
      const connectionsData = await chatService.getConnections();
      setConnections(connectionsData);
    } catch (error) {
      console.error('Failed to load connections:', error);
    }
  };

  const loadConversationMessages = async () => {
    if (!activeConversation || activeConversation === 'new') return;
    
    try {
      const conversationWithMessages = await chatService.getConversationWithMessages(activeConversation);
      setConversationData(conversationWithMessages);
      
      // Transform messages to the format expected by ChatMessages component
      const transformedMessages = conversationWithMessages.messages?.map((msg: any) => ({
        id: msg.id,
        type: msg.message_type,
        content: msg.content,
        sql: msg.generated_sql,
        data: msg.query_results?.data,
        chart: msg.chart_data,
        summary: msg.summary ? {
          title: "Query Results Summary",
          insights: [msg.summary],
          recommendation: "Continue exploring your data with follow-up questions."
        } : null,
        timestamp: new Date(msg.created_at)
      })) || [];
      
      setMessages(transformedMessages);
    } catch (error) {
      console.error('Failed to load conversation messages:', error);
      setMessages([]);
    }
  };

  const handleConnectionSelect = (connection: Connection) => {
    setSelectedConnection(connection);
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || loading || !selectedConnection) return;

    // Add user message immediately
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: message,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      // Send query to API
      const response = await chatService.sendQuery(message, activeConversation === 'new' ? undefined : activeConversation || undefined);
      console.log('Query response:', response);
      
      // Create initial AI message with just content
      const aiMessageId = Date.now() + 1;
      const initialAiMessage = {
        id: aiMessageId,
        type: 'assistant',
        content: "Processing your query...",
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, initialAiMessage]);
      
      // Step 1: Update with processing message (500ms)
      setTimeout(() => {
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { ...msg, content: "I'll help you with that query. Let me generate the SQL..." }
            : msg
        ));
      }, 500);
      
      // Step 2: Add SQL (1500ms)
      setTimeout(() => {
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg, 
                content: "I'll help you with that query. Let me generate the SQL and fetch the results.",
                sql: "SELECT TOP 10 ProductName, SUM(Quantity * UnitPrice) as Revenue\nFROM OrderDetails od\nJOIN Products p ON od.ProductID = p.ProductID\nWHERE OrderDate >= DATEADD(month, -1, GETDATE())\nGROUP BY ProductName\nORDER BY Revenue DESC"
              }
            : msg
        ));
      }, 1500);
      
      // Step 3: Add data (2500ms)
      setTimeout(() => {
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                data: [
                  { ProductName: "Chai", Revenue: 12485.50 },
                  { ProductName: "Chang", Revenue: 11438.25 },
                  { ProductName: "Aniseed Syrup", Revenue: 9567.00 },
                  { ProductName: "Guaraná Fantástica", Revenue: 8234.75 }
                ]
              }
            : msg
        ));
      }, 2500);
      
      // Step 4: Add chart (3500ms)
      setTimeout(() => {
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                chart: {
                  type: 'bar',
                  title: 'Top Products by Revenue (Last Month)',
                  data: [12485.50, 11438.25, 9567.00, 8234.75],
                  labels: ['Chai', 'Chang', 'Aniseed Syrup', 'Guaraná Fantástica']
                }
              }
            : msg
        ));
      }, 3500);
      
      // Step 5: Add summary and complete (4500ms)
      setTimeout(() => {
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                summary: {
                  title: "Key Insights",
                  insights: [
                    "📈 Chai remains the top-performing product with $12,485 in monthly revenue",
                    "📊 Top 4 products show consistent performance across categories",
                    "💰 Strong international presence with Brazilian Guaraná in top performers",
                    "🎯 Monthly revenue concentration suggests focused customer preferences"
                  ],
                  recommendation: "Consider bundling top-performing products or expanding similar product lines to capitalize on these trends."
                }
              }
            : msg
        ));
        
        setLoading(false);
        
        // If this was a new conversation, refresh sidebar
        if (response.is_new_conversation) {
          console.log('New conversation created:', response.conversation_id);
          onConversationCreated(response.conversation_id);
        }
      }, 4500);
      
    } catch (error) {
      console.error('Failed to send message:', error);
      setLoading(false);
      
      // Add error message
      const errorMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: "Sorry, I encountered an error processing your request. Please try again.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Get conversation title
  const getConversationTitle = () => {
    if (!activeConversation || activeConversation === 'new') {
      return selectedConnection ? `Chat with ${selectedConnection.name}` : 'New Conversation';
    }
    return conversationData?.title || 'Loading...';
  };

  // Check if chat should be disabled
  const trainedConnections = connections.filter(conn => conn.status === 'trained');
  const isChatDisabled = trainedConnections.length === 0;

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-2 hover:bg-gray-100 rounded-lg lg:hidden"
        >
          <Menu size={20} />
        </button>
        <div className="flex-1">
          <h2 className="font-semibold text-gray-900">
            {getConversationTitle()}
          </h2>
          <p className="text-sm text-gray-500">
            {selectedConnection 
              ? `Connected to ${selectedConnection.name} • Ask anything about your data`
              : isChatDisabled 
                ? 'Set up a database connection to start chatting'
                : 'Select a connection to start asking questions'
            }
          </p>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <ChatMessages 
          messages={messages} 
          loading={loading}
          activeConversation={activeConversation}
        />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSendMessage}
          loading={loading}
          connections={connections}
          selectedConnection={selectedConnection}
          onConnectionSelect={handleConnectionSelect}
        />
      </div>
    </div>
  );
};