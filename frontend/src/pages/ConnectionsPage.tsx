import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Database, ArrowLeft, MoreVertical, Play, Zap, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { Connection } from '../types/chat';
import { chatService } from '../services/chat';
import { ConnectionSetupModal } from '../components/connection/ConnectionSetupModal';

export const ConnectionsPage: React.FC = () => {
  const navigate = useNavigate();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [showActions, setShowActions] = useState<string | null>(null);
  const [showSetupModal, setShowSetupModal] = useState(false);

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      const connectionsData = await chatService.getConnections();
      setConnections(connectionsData);
    } catch (error) {
      console.error('Failed to load connections:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'trained':
        return { 
          icon: CheckCircle, 
          color: 'text-green-600', 
          bg: 'bg-green-100', 
          text: 'Trained',
          description: 'Ready for queries'
        };
      case 'training':
        return { 
          icon: Zap, 
          color: 'text-yellow-600', 
          bg: 'bg-yellow-100', 
          text: 'Training',
          description: 'Model training in progress'
        };
      case 'data_generated':
        return { 
          icon: Play, 
          color: 'text-blue-600', 
          bg: 'bg-blue-100', 
          text: 'Ready to Train',
          description: 'Training data ready'
        };
      case 'test_success':
        return { 
          icon: CheckCircle, 
          color: 'text-blue-600', 
          bg: 'bg-blue-100', 
          text: 'Connected',
          description: 'Connection tested successfully'
        };
      case 'generating_data':
        return { 
          icon: Clock, 
          color: 'text-yellow-600', 
          bg: 'bg-yellow-100', 
          text: 'Generating',
          description: 'Creating training examples'
        };
      case 'testing':
        return { 
          icon: Clock, 
          color: 'text-gray-600', 
          bg: 'bg-gray-100', 
          text: 'Testing',
          description: 'Testing connection'
        };
      case 'test_failed':
      case 'training_failed':
        return { 
          icon: AlertCircle, 
          color: 'text-red-600', 
          bg: 'bg-red-100', 
          text: 'Failed',
          description: 'Action required'
        };
      default:
        return { 
          icon: Clock, 
          color: 'text-gray-600', 
          bg: 'bg-gray-100', 
          text: 'Unknown',
          description: 'Status unknown'
        };
    }
  };

  const handleConnectionClick = (connectionId: string) => {
    console.log('Navigate to connection detail:', connectionId);
    navigate(`/connections/${connectionId}`);
  };

  const handleConnectionCreated = (connectionId: string) => {
    console.log('Connection created:', connectionId);
    setShowSetupModal(false);
    loadConnections(); // Reload the connections list
    // Navigate to the connection detail page
    navigate(`/connections/${connectionId}`);
  };

  const handleActionClick = (action: string, connectionId: string) => {
    console.log('Action:', action, 'for connection:', connectionId);
    setShowActions(null);
    
    switch (action) {
      case 'view':
        handleConnectionClick(connectionId);
        break;
      case 'retrain':
        // TODO: Start retraining
        break;
      case 'delete':
        // TODO: Delete connection
        break;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading connections...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft size={20} className="text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Database Connections</h1>
                <p className="text-sm text-gray-500">Manage your database connections and AI models</p>
              </div>
            </div>
            <button
              onClick={() => setShowSetupModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Plus size={16} />
              Add Connection
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {connections.length === 0 ? (
          // Empty State
          <div className="text-center py-12">
            <Database size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No connections yet</h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Create your first database connection to start asking questions about your data with AI.
            </p>
            <button
              onClick={() => setShowSetupModal(true)}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors mx-auto"
            >
              <Plus size={20} />
              Create Your First Connection
            </button>
          </div>
        ) : (
          // Connections Grid
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {connections.map(connection => {
              const statusInfo = getStatusInfo(connection.status);
              const StatusIcon = statusInfo.icon;
              
              return (
                <div
                  key={connection.id}
                  className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
                  onClick={(e) => {
                    console.log('Card clicked for connection:', connection.id);
                    // Check if click is on the actions button
                    if ((e.target as HTMLElement).closest('button')) {
                      console.log('Click was on a button, not navigating');
                      return;
                    }
                    handleConnectionClick(connection.id);
                  }}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Database size={20} className="text-blue-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900 truncate">{connection.name}</h3>
                        <p className="text-sm text-gray-500 truncate">{connection.server}</p>
                      </div>
                    </div>
                    
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowActions(showActions === connection.id ? null : connection.id);
                        }}
                        className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        <MoreVertical size={16} className="text-gray-400" />
                      </button>
                      
                      {/* Actions Dropdown */}
                      {showActions === connection.id && (
                        <div className="absolute right-0 top-8 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-[120px]">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleActionClick('view', connection.id);
                            }}
                            className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 first:rounded-t-lg"
                          >
                            View Details
                          </button>
                          {connection.status === 'trained' && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleActionClick('retrain', connection.id);
                              }}
                              className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50"
                            >
                              Retrain Model
                            </button>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleActionClick('delete', connection.id);
                            }}
                            className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 last:rounded-b-lg"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Status */}
                  <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm ${statusInfo.bg} ${statusInfo.color} mb-4`}>
                    <StatusIcon size={14} />
                    <span className="font-medium">{statusInfo.text}</span>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-4">{statusInfo.description}</p>

                  {/* Details */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Database:</span>
                      <span className="text-gray-900">{connection.database_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Table:</span>
                      <span className="text-gray-900">{connection.table_name}</span>
                    </div>
                    {connection.total_queries > 0 && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">Queries:</span>
                        <span className="text-gray-900">{connection.total_queries}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-500">Created:</span>
                      <span className="text-gray-900">
                        {new Date(connection.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Click outside to close actions */}
      {showActions && (
        <div 
          className="fixed inset-0 z-5" 
          onClick={() => setShowActions(null)}
        />
      )}

      {/* Connection Setup Modal */}
      <ConnectionSetupModal
        isOpen={showSetupModal}
        onClose={() => setShowSetupModal(false)}
        onConnectionCreated={handleConnectionCreated}
      />
    </div>
  );
};