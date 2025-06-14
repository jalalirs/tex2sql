import React from 'react';
import { Database, X, Clock, CheckCircle } from 'lucide-react';
import { Connection } from '../../types/chat';

interface ConnectionSelectionModalProps {
  isOpen: boolean;
  connections: Connection[];
  onClose: () => void;
  onSelectConnection: (connectionId: string) => void;
}

export const ConnectionSelectionModal: React.FC<ConnectionSelectionModalProps> = ({
  isOpen,
  connections,
  onClose,
  onSelectConnection
}) => {
  if (!isOpen) return null;

  const getConnectionStatusInfo = (status: string) => {
    switch (status) {
      case 'trained':
        return { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-50', text: 'Ready' };
      case 'training':
        return { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-50', text: 'Training' };
      case 'test_success':
        return { icon: CheckCircle, color: 'text-blue-600', bg: 'bg-blue-50', text: 'Tested' };
      default:
        return { icon: Clock, color: 'text-gray-600', bg: 'bg-gray-50', text: 'Processing' };
    }
  };

  const trainedConnections = connections.filter(conn => conn.status === 'trained');
  const otherConnections = connections.filter(conn => conn.status !== 'trained');

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Select Connection</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-96">
          {connections.length === 0 ? (
            <div className="text-center py-8">
              <Database size={48} className="mx-auto text-gray-400 mb-3" />
              <p className="text-gray-600 mb-4">No connections available</p>
              <p className="text-sm text-gray-500">
                You need to create and train a database connection before starting a conversation.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Trained connections first */}
              {trainedConnections.length > 0 && (
                <>
                  <div className="text-sm font-medium text-gray-700 mb-2">Ready for Queries</div>
                  {trainedConnections.map(connection => {
                    const statusInfo = getConnectionStatusInfo(connection.status);
                    const StatusIcon = statusInfo.icon;
                    
                    return (
                      <button
                        key={connection.id}
                        onClick={() => onSelectConnection(connection.id)}
                        className="w-full p-3 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-left"
                      >
                        <div className="flex items-center gap-3">
                          <Database size={20} className="text-blue-600" />
                          <div className="flex-1">
                            <div className="font-medium text-gray-900">{connection.name}</div>
                            <div className="text-sm text-gray-500">{connection.server}</div>
                          </div>
                          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${statusInfo.bg}`}>
                            <StatusIcon size={12} className={statusInfo.color} />
                            <span className={statusInfo.color}>{statusInfo.text}</span>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </>
              )}

              {/* Other connections */}
              {otherConnections.length > 0 && (
                <>
                  {trainedConnections.length > 0 && (
                    <div className="text-sm font-medium text-gray-500 mb-2 mt-4">Not Ready</div>
                  )}
                  {otherConnections.map(connection => {
                    const statusInfo = getConnectionStatusInfo(connection.status);
                    const StatusIcon = statusInfo.icon;
                    
                    return (
                      <div
                        key={connection.id}
                        className="w-full p-3 border border-gray-200 rounded-lg bg-gray-50 text-left opacity-60 cursor-not-allowed"
                      >
                        <div className="flex items-center gap-3">
                          <Database size={20} className="text-gray-400" />
                          <div className="flex-1">
                            <div className="font-medium text-gray-700">{connection.name}</div>
                            <div className="text-sm text-gray-500">{connection.server}</div>
                          </div>
                          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${statusInfo.bg}`}>
                            <StatusIcon size={12} className={statusInfo.color} />
                            <span className={statusInfo.color}>{statusInfo.text}</span>
                          </div>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Complete training to use this connection
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {connections.length > 0 && (
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <p className="text-xs text-gray-600 text-center">
              Select a trained connection to start a new conversation
            </p>
          </div>
        )}
      </div>
    </div>
  );
};