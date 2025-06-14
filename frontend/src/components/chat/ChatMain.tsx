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
      // Send query to API with connection_id
      const response = await chatService.sendQuery(
        message, 
        activeConversation === 'new' ? undefined : activeConversation || undefined,
        selectedConnection.id
      );
      console.log('Query response:', response);
      
      // Create initial AI message
      const aiMessageId = Date.now() + 1;
      const initialAiMessage = {
        id: aiMessageId,
        type: 'assistant',
        content: "Processing your query...",
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, initialAiMessage]);
      
      // Connect to SSE stream
      if (response.session_id && response.stream_url) {
        const eventSource = new EventSource(response.stream_url);
        
        eventSource.onopen = () => {
          console.log('SSE connection opened');
        };
        
        eventSource.addEventListener('query_progress', (event) => {
          const data = JSON.parse(event.data);
          console.log('Query progress:', data);
          
          // Update message content based on progress
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { ...msg, content: data.message || data.step || "Processing..." }
              : msg
          ));
        });
        
        eventSource.addEventListener('sql_generated', (event) => {
          const data = JSON.parse(event.data);
          console.log('SQL generated:', data);
          
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { 
                  ...msg, 
                  content: "I'll help you with that query. Let me generate the SQL and fetch the results.",
                  sql: data.sql
                }
              : msg
          ));
        });
        
        eventSource.addEventListener('data_fetched', (event) => {
          const data = JSON.parse(event.data);
          console.log('Data fetched:', data);
          
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { 
                  ...msg,
                  data: data.query_results?.data || data.data
                }
              : msg
          ));
        });
        
        eventSource.addEventListener('chart_generated', (event) => {
          const data = JSON.parse(event.data);
          console.log('Chart generated:', data);
          
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { 
                  ...msg,
                  chart: data.chart_data || data.chart
                }
              : msg
          ));
        });
        
        eventSource.addEventListener('query_completed', (event) => {
          const data = JSON.parse(event.data);
          console.log('Query completed:', data);
          
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { 
                  ...msg,
                  summary: {
                    title: "Query Results",
                    insights: [
                      data.summary || `Query executed on ${selectedConnection.name}`,
                      `Found ${data.row_count || 0} results`,
                      `Execution time: ${data.execution_time || 0}ms`
                    ],
                    recommendation: "Ask follow-up questions to explore your data further."
                  }
                }
              : msg
          ));
          
          setLoading(false);
          eventSource.close();
          
          // Handle new conversation
          if (data.is_new_conversation || response.is_new_conversation) {
            console.log('New conversation created:', data.conversation_id || response.conversation_id);
            onConversationCreated(data.conversation_id || response.conversation_id);
          }
        });
        
        eventSource.addEventListener('query_error', (event) => {
          const data = JSON.parse(event.data);
          console.error('Query error:', data);
          
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { 
                  ...msg,
                  content: `Error: ${data.error || 'Failed to process query'}`
                }
              : msg
          ));
          
          setLoading(false);
          eventSource.close();
        });
        
        eventSource.onerror = (error) => {
          console.error('SSE error:', error);
          setLoading(false);
          eventSource.close();
          
          // Add error message
          const errorMessage = {
            id: Date.now() + 2,
            type: 'assistant',
            content: "Connection lost. Please try again.",
            timestamp: new Date()
          };
          setMessages(prev => [...prev, errorMessage]);
        };
        
        // Cleanup function
        const cleanup = () => {
          eventSource.close();
          setLoading(false);
        };
        
        // Auto-cleanup after 30 seconds
        setTimeout(cleanup, 30000);
        
      } else {
        // Fallback for immediate response (if no SSE)
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                content: "I'll help you with that query. Let me generate the SQL and fetch the results.",
                sql: response.generated_sql || `SELECT TOP 10 * FROM ${selectedConnection.table_name}`,
                data: response.query_results?.data || [{ Message: "No SSE stream available" }],
                chart: response.chart_data,
                summary: {
                  title: "Query Results",
                  insights: [response.summary || "Query completed"],
                  recommendation: "Ask follow-up questions to explore your data further."
                }
              }
            : msg
        ));
        
        setLoading(false);
        
        if (response.is_new_conversation) {
          onConversationCreated(response.conversation_id);
        }
      }
      
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