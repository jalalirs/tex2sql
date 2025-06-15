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
  const [justCreatedConversation, setJustCreatedConversation] = useState<string | null>(null);

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
    console.log('useEffect triggered - activeConversation:', activeConversation, 'justCreatedConversation:', justCreatedConversation);
    
    if (activeConversation && activeConversation !== 'new') {
      // Don't reload if we just created this conversation (messages are already in state)
      if (justCreatedConversation === activeConversation) {
        console.log('✅ Skipping reload for just-created conversation - keeping existing messages');
        setJustCreatedConversation(null); // Reset the flag
        return;
      }
      console.log('📥 Loading conversation messages for existing conversation:', activeConversation);
      loadConversationMessages();
    } else if (activeConversation === 'new') {
      console.log('🆕 New conversation state - clearing messages');
      setMessages([]);
      setConversationData(null);
    }
    // Note: Don't clear messages when activeConversation is null (landing page)
  }, [activeConversation]);
  
  const loadConnections = async () => {
    try {
      console.log('Loading connections...');
      const connectionsData: any = await chatService.getConnections();
      console.log('Connections data:', connectionsData);
      
      // Handle the backend response format: {connections: [...], total: number}
      let connections: Connection[] = []; // Add explicit type here
      if (connectionsData && Array.isArray(connectionsData.connections)) {
        connections = connectionsData.connections;
      } else if (Array.isArray(connectionsData)) {
        connections = connectionsData;
      } else {
        console.error('Unexpected connections data format:', connectionsData);
        connections = []; // Ensure it's always an array
      }
      
      setConnections(connections);
    } catch (error) {
      console.error('Failed to load connections:', error);
      setConnections([]);
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
    console.log('handleSendMessage called with:', { message, loading, selectedConnection });
    
    if (!message.trim() || loading || !selectedConnection) {
      console.log('Aborting send - conditions not met');
      return;
    }
  
    console.log('Proceeding with message send...');
  
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
      
      const aiMessageId = Date.now() + 1;
      
      // Connect to SSE stream
      // Replace the SSE connection block in handleSendMessage with this:

      // Replace the entire SSE block in handleSendMessage with this fetch streaming approach:

    // Replace the entire SSE block in handleSendMessage with this fetch streaming approach:

    // Replace the entire SSE block in handleSendMessage with this EventSource version:

if (response.session_id && response.stream_url) {
  try {
    console.log('Setting up EventSource connection...');
    const fullStreamUrl = response.stream_url.startsWith('http') 
      ? response.stream_url 
      : `http://localhost:6020${response.stream_url}`;
    
    console.log('EventSource URL:', fullStreamUrl);
    
    const eventSource = new EventSource(fullStreamUrl);
    console.log('EventSource created, readyState:', eventSource.readyState);
    
    let connected = false;
    
    eventSource.onopen = () => {
      console.log('✅ EventSource opened successfully');
      connected = true;
    };
    
    eventSource.onmessage = (event) => {
      console.log('📨 EventSource message:', event);
      try {
        const data = JSON.parse(event.data);
        console.log('📨 Parsed data:', data);
        
        // Handle generic data updates (fallback)
        if (data.message) {
          setMessages(prev => prev.map(msg => 
            msg.id === aiMessageId 
              ? { ...msg, content: data.message }
              : msg
          ));
        }
      } catch (e) {
        console.error('Error parsing message:', e);
      }
    };
    
    eventSource.addEventListener('connected', (event) => {
      console.log('🔗 Connected event:', event.data);
    });
    
    eventSource.addEventListener('query_progress', (event) => {
      console.log('⏳ Query progress event:', event.data);
      try {
        const data = JSON.parse(event.data);
        
        // Check if AI message exists, if not create it
        setMessages(prev => {
          const hasAiMessage = prev.some(msg => msg.id === aiMessageId);
          if (!hasAiMessage) {
            // Add AI message on first progress event
            return [...prev, {
              id: aiMessageId,
              type: 'assistant',
              content: data.message || "Processing...",
              timestamp: new Date()
            }];
          } else {
            // Update existing AI message
            return prev.map(msg => 
              msg.id === aiMessageId 
                ? { ...msg, content: data.message || "Processing..." }
                : msg
            );
          }
        });
      } catch (e) {
        console.error('Error in query_progress:', e);
      }
    });
    
    eventSource.addEventListener('sql_generated', (event) => {
      console.log('📝 SQL generated event:', event.data);
      try {
        const data = JSON.parse(event.data);
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg, 
                content: "I'll help you with that query. Let me generate the SQL and fetch the results.",
                sql: data.sql
              }
            : msg
        ));
      } catch (e) {
        console.error('Error in sql_generated:', e);
      }
    });
    
    eventSource.addEventListener('data_fetched', (event) => {
      console.log('📊 Data fetched event:', event.data);
      try {
        const data = JSON.parse(event.data);
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                data: data.query_results?.data || data.data
              }
            : msg
        ));
      } catch (e) {
        console.error('Error in data_fetched:', e);
      }
    });
    
    eventSource.addEventListener('chart_generated', (event) => {
      console.log('📈 Chart generated event:', event.data);
      try {
        const data = JSON.parse(event.data);
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { 
                ...msg,
                chart: data.chart_data || data.chart
              }
            : msg
        ));
      } catch (e) {
        console.error('Error in chart_generated:', e);
      }
    });
    
    eventSource.addEventListener('query_completed', (event) => {
      console.log('✅ Query completed event:', event.data);
      try {
        const data = JSON.parse(event.data);
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
        
        if (data.is_new_conversation || response.is_new_conversation) {
          const newConvId = data.conversation_id || response.conversation_id;
          console.log('🆕 New conversation created:', newConvId);
          setJustCreatedConversation(newConvId);
          onConversationCreated(newConvId);
        }
        eventSource.close();
      } catch (e) {
        console.error('Error in query_completed:', e);
      }
    });
    
    eventSource.onerror = (error) => {
      console.error('❌ EventSource error:', error);
      console.error('EventSource readyState:', eventSource.readyState);
      
      if (!connected) {
        setLoading(false);
        setMessages(prev => prev.map(msg => 
          msg.id === aiMessageId 
            ? { ...msg, content: "Connection failed. Please try again." }
            : msg
        ));
      }
      eventSource.close();
    };
    
    // Timeout after 30 seconds
    setTimeout(() => {
      if (eventSource.readyState !== EventSource.CLOSED) {
        console.log('⏰ EventSource timeout');
        eventSource.close();
        setLoading(false);
      }
    }, 30000);
    
  } catch (error) {
    console.error('❌ EventSource setup error:', error);
    setLoading(false);
    setMessages(prev => prev.map(msg => 
      msg.id === aiMessageId 
        ? { ...msg, content: "Failed to set up connection. Please try again." }
        : msg
    ));
  }
}else {
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