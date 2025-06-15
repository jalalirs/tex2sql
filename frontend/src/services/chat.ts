import { api } from './auth';
import { Connection, Conversation } from '../types/chat';

export const chatService = {
  // Get user's connections (determined by token)
  async getConnections(): Promise<{connections: Connection[], total: number}> {
    const response = await api.get('/connections');
    return response.data;
  },

  // Get user's conversations (determined by token)  
  async getConversations(connectionId?: string): Promise<Conversation[]> {
    const params = connectionId ? { connection_id: connectionId } : {};
    const response = await api.get('/conversations', { params });
    return response.data;
  },

  // Get conversation with messages
  async getConversationWithMessages(conversationId: string) {
    const response = await api.get(`/conversations/${conversationId}`);
    return response.data;
  },

  // Create new conversation
  async createConversation(connectionId: string, title?: string): Promise<Conversation> {
    const response = await api.post('/conversations', {
      connection_id: connectionId,
      title
    });
    return response.data;
  },

  // Send message/query - FIXED: Added connection_id parameter
  async sendQuery(question: string, conversationId?: string, connectionId?: string) {
    const response = await api.post('/conversations/query', {
      question,
      conversation_id: conversationId,
      connection_id: connectionId // Add connection_id to request
    });
    return response.data;
  }
};