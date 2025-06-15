import React, { useState } from 'react';
import { X, Database, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../../services/auth';


interface ConnectionSetupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnectionCreated: (connectionId: string) => void;
}

interface ConnectionFormData {
  name: string;
  server: string;
  database_name: string;
  username: string;
  password: string;
  table_name: string;
  driver: string;
}

interface TestResult {
  success: boolean;
  error?: string;
  sampleData?: any[];
  columnInfo?: any;
}

export const ConnectionSetupModal: React.FC<ConnectionSetupModalProps> = ({
  isOpen,
  onClose,
  onConnectionCreated
}) => {
  const [formData, setFormData] = useState<ConnectionFormData>({
    name: 'employees',
    server: 'localhost,1433',
    database_name: 'TestCompanyDB',
    username: 'sa',
    password: 'l.messi10',
    table_name: 'Employees',
    driver: 'ODBC Driver 18 for SQL Server'
  });

  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [creating, setCreating] = useState(false);

  if (!isOpen) return null;

  const handleInputChange = (field: keyof ConnectionFormData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear test results when form changes
    if (testResult) {
      setTestResult(null);
    }
  };

  const isFormValid = () => {
    return !!(formData.name && formData.server && formData.database_name && 
             formData.username && formData.password && formData.table_name);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
  
    try {
      // Start the connection test
      const response = await api.post('/connections/test', {
        connection_data: {
          name: formData.name,
          server: formData.server,
          database_name: formData.database_name,
          username: formData.username,
          password: formData.password,
          table_name: formData.table_name,
          driver: formData.driver
        }
      });
  
      const taskId = response.data.task_id;
      console.log('🔍 Connection test started, task ID:', taskId);
  
      // Connect to SSE stream for test results
      if (taskId) {
        const streamUrl = `http://localhost:6020/events/stream/${taskId}`;
        console.log('🔗 Connecting to SSE stream:', streamUrl);
        
        const eventSource = new EventSource(streamUrl);
        
        eventSource.onopen = () => {
          console.log('✅ SSE connection opened for connection test');
        };
  
        // Generic message handler (fallback)
        eventSource.onmessage = (event) => {
          console.log('📨 Generic SSE message:', event.data);
          try {
            const data = JSON.parse(event.data);
            // Handle completion here as fallback
            if (data.success !== undefined) {
              if (data.success) {
                setTestResult({
                  success: true,
                  sampleData: data.sample_data || [],
                  columnInfo: data.column_info || {}
                });
              } else {
                setTestResult({
                  success: false,
                  error: data.error_message || data.error || 'Connection test failed'
                });
              }
              setTesting(false);
              eventSource.close();
            }
          } catch (e) {
            console.error('Error parsing generic message:', e);
          }
        };
        
        eventSource.addEventListener('connected', (event) => {
          console.log('🔗 Connected to test stream:', event.data);
        });
  
        eventSource.addEventListener('progress', (event) => {
          console.log('⏳ Test progress:', event.data);
          // Optional: show progress to user
        });
  
        eventSource.addEventListener('test_completed', (event) => {
          console.log('✅ Test completed:', event.data);
          try {
            const data = JSON.parse(event.data);
            if (data.success) {
              setTestResult({
                success: true,
                sampleData: data.sample_data || [],
                columnInfo: data.column_info || {}
              });
            } else {
              setTestResult({
                success: false,
                error: data.error_message || 'Connection test failed'
              });
            }
          } catch (e) {
            console.error('Error parsing test completion event:', e);
          }
          setTesting(false);
          eventSource.close();
        });
  
        eventSource.addEventListener('connection_test_completed', (event) => {
          console.log('✅ Connection test completed:', event.data);
          try {
            const data = JSON.parse(event.data);
            if (data.success) {
              setTestResult({
                success: true,
                sampleData: data.sample_data || [],
                columnInfo: data.column_info || {}
              });
            } else {
              setTestResult({
                success: false,
                error: data.error_message || 'Connection test failed'
              });
            }
          } catch (e) {
            console.error('Error parsing connection test completion event:', e);
          }
          setTesting(false);
          eventSource.close();
        });
  
        eventSource.addEventListener('test_failed', (event) => {
          console.log('❌ Test failed:', event.data);
          try {
            const data = JSON.parse(event.data);
            setTestResult({
              success: false,
              error: data.error || data.message || 'Connection test failed'
            });
          } catch (e) {
            setTestResult({
              success: false,
              error: 'Connection test failed'
            });
          }
          setTesting(false);
          eventSource.close();
        });
  
        eventSource.addEventListener('connection_test_failed', (event) => {
          console.log('❌ Connection test failed:', event.data);
          try {
            const data = JSON.parse(event.data);
            setTestResult({
              success: false,
              error: data.error || data.message || 'Connection test failed'
            });
          } catch (e) {
            setTestResult({
              success: false,
              error: 'Connection test failed'
            });
          }
          setTesting(false);
          eventSource.close();
        });
  
        eventSource.addEventListener('error', (event: any) => {
          console.log('❌ Test error event:', event.data);
          try {
            const data = JSON.parse(event.data);
            setTestResult({
              success: false,
              error: data.error || data.message || 'Connection test failed'
            });
          } catch (e) {
            setTestResult({
              success: false,
              error: 'Connection test failed'
            });
          }
          setTesting(false);
          eventSource.close();
        });
        
        eventSource.onerror = (error) => {
          console.error('❌ SSE error during connection test:', error);
          console.error('EventSource readyState:', eventSource.readyState);
          
          setTestResult({
            success: false,
            error: 'Connection test failed - stream error'
          });
          setTesting(false);
          eventSource.close();
        };
        
        // Timeout after 30 seconds
        setTimeout(() => {
          if (eventSource.readyState !== EventSource.CLOSED) {
            console.log('⏰ Connection test timeout');
            eventSource.close();
            setTestResult({
              success: false,
              error: 'Connection test timed out'
            });
            setTesting(false);
          }
        }, 30000);
      } else {
        // No task ID returned
        setTestResult({
          success: false,
          error: 'No task ID returned from server'
        });
        setTesting(false);
      }
      
    } catch (error: any) {
      console.error('Connection test error:', error);
      setTestResult({
        success: false,
        error: error.response?.data?.detail || `Connection test failed: ${error.message}`
      });
      setTesting(false);
    }
  };

  const handleCreateConnection = async () => {
    setCreating(true);
  
    try {
      // Create FormData instead of JSON
      const formDataToSend = new FormData();
      formDataToSend.append('name', formData.name);
      formDataToSend.append('server', formData.server);
      formDataToSend.append('database_name', formData.database_name);
      formDataToSend.append('username', formData.username);
      formDataToSend.append('password', formData.password);
      formDataToSend.append('table_name', formData.table_name);
      formDataToSend.append('driver', formData.driver);
  
      console.log('🔍 Creating connection with FormData:');
      // Use Array.from to fix TypeScript iteration issue
      Array.from(formDataToSend.entries()).forEach(([key, value]) => {
        console.log(`${key}: ${value}`);
      });
  
      // Send FormData (not JSON)
      const response = await api.post('/connections', formDataToSend, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
  
      const connectionData = response.data;
      console.log('Connection created successfully:', connectionData);
      
      onConnectionCreated(connectionData.id);
    } catch (error: any) {
      console.error('Failed to create connection:', error);
      console.error('Error response:', error.response?.data);
      alert(`Failed to create connection: ${error.response?.data?.detail || error.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    // Reset form
    setFormData({
      name: 'employees',
      server: 'localhost,1433',
      database_name: 'TestCompanyDB',
      username: 'sa',
      password: 'l.messi10',
      table_name: 'Employees',
      driver: 'ODBC Driver 18 for SQL Server'
    });
    setTestResult(null);
    setTesting(false);
    setCreating(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Add Database Connection</h2>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X size={20} className="text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Form */}
          <div className="space-y-6 mb-6">
            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Connection Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="Production Database"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Server *
                </label>
                <input
                  type="text"
                  value={formData.server}
                  onChange={(e) => handleInputChange('server', e.target.value)}
                  placeholder="localhost or server.company.com"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Database Name *
                </label>
                <input
                  type="text"
                  value={formData.database_name}
                  onChange={(e) => handleInputChange('database_name', e.target.value)}
                  placeholder="ecommerce"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Table Name *
                </label>
                <input
                  type="text"
                  value={formData.table_name}
                  onChange={(e) => handleInputChange('table_name', e.target.value)}
                  placeholder="schema.tablename"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Username *
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => handleInputChange('username', e.target.value)}
                  placeholder="database_user"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password *
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => handleInputChange('password', e.target.value)}
                  placeholder="••••••••"
                  className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Driver
              </label>
              <select
                value={formData.driver}
                onChange={(e) => handleInputChange('driver', e.target.value)}
                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="ODBC Driver 17 for SQL Server">ODBC Driver 17 for SQL Server</option>
                <option value="ODBC Driver 18 for SQL Server">ODBC Driver 18 for SQL Server</option>
                <option value="SQL Server Native Client 11.0">SQL Server Native Client 11.0</option>
              </select>
            </div>
          </div>

          {/* Test Results */}
          {testResult && (
            <div className="mb-6 bg-gray-50 rounded-lg p-4">
              {testResult.success ? (
                <div>
                  <div className="flex items-center gap-2 text-green-600 mb-4">
                    <CheckCircle size={20} />
                    <h3 className="font-medium">Connection Successful!</h3>
                  </div>
                  
                  {testResult.sampleData && testResult.sampleData.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Sample Data ({testResult.sampleData.length} rows):
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="min-w-full border border-gray-200 rounded-lg">
                          <thead className="bg-white">
                            <tr>
                              {testResult.sampleData[0] && Object.keys(testResult.sampleData[0]).map(key => (
                                <th key={key} className="px-3 py-2 text-left text-xs font-medium text-gray-700 border-b">
                                  {key}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {testResult.sampleData.map((row, idx) => (
                              <tr key={idx} className="border-b">
                                {row && Object.values(row).map((value: any, vidx) => (
                                  <td key={vidx} className="px-3 py-2 text-xs">
                                    {typeof value === 'number' && value > 100 
                                      ? value.toLocaleString() 
                                      : String(value)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <div className="text-sm text-gray-600">
                    ✓ Connection verified and ready to be added
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle size={20} />
                  <div>
                    <h3 className="font-medium">Connection Failed</h3>
                    <p className="text-sm mt-1">{testResult.error}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          
          <div className="flex gap-3">
            <button
              onClick={handleTestConnection}
              disabled={!isFormValid() || testing}
              className={`flex items-center gap-2 px-4 py-2 border rounded-lg transition-colors ${
                !isFormValid() || testing
                  ? 'border-gray-300 bg-gray-50 text-gray-400 cursor-not-allowed'
                  : 'border-blue-600 text-blue-600 hover:bg-blue-50'
              }`}
            >
              {testing ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Database size={16} />
              )}
              {testing ? 'Testing...' : 'Test Connection'}
            </button>

            <button
              onClick={handleCreateConnection}
              disabled={!testResult?.success || creating}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                !testResult?.success || creating
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {creating ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <CheckCircle size={16} />
              )}
              {creating ? 'Adding...' : 'Add Connection'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};