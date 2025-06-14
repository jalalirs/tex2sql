import React, { useState } from 'react';
import { X, Database, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

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
      // Make real API call to test connection
      const response = await fetch('http://localhost:6020/connections/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}` // Add auth if needed
        },
        body: JSON.stringify({
          connection_data: {
            name: formData.name,
            server: formData.server,
            database_name: formData.database_name,
            username: formData.username,
            password: formData.password,
            table_name: formData.table_name,
            driver: formData.driver
          }
        })
      });

      const result = await response.json();

      if (result.success) {
        setTestResult({
          success: true,
          sampleData: result.sample_data || [],
          columnInfo: result.column_info || {}
        });
      } else {
        setTestResult({
          success: false,
          error: result.error_message || 'Connection test failed'
        });
      }
    } catch (error: any) {
      console.error('Connection test error:', error);
      setTestResult({
        success: false,
        error: `Connection test failed: ${error.message}`
      });
    } finally {
      setTesting(false);
    }
  };

  const handleCreateConnection = async () => {
    setCreating(true);

    try {
      // Make real API call to create connection
      const response = await fetch('http://localhost:6020/connections', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}` // Add auth if needed
        },
        body: JSON.stringify({
          name: formData.name,
          server: formData.server,
          database_name: formData.database_name,
          username: formData.username,
          password: formData.password,
          table_name: formData.table_name,
          driver: formData.driver
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create connection');
      }

      const connectionData = await response.json();
      console.log('Connection created successfully:', connectionData);
      
      // Call the callback with the actual connection ID
      onConnectionCreated(connectionData.id);
    } catch (error: any) {
      console.error('Failed to create connection:', error);
      // TODO: Show error message to user
      alert(`Failed to create connection: ${error.message}`);
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
                  
                  {testResult.sampleData && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Sample Data ({testResult.sampleData.length} rows):
                      </h4>
                      <div className="overflow-x-auto">
                        <table className="min-w-full border border-gray-200 rounded-lg">
                          <thead className="bg-white">
                            <tr>
                              {Object.keys(testResult.sampleData[0]).map(key => (
                                <th key={key} className="px-3 py-2 text-left text-xs font-medium text-gray-700 border-b">
                                  {key}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {testResult.sampleData.map((row, idx) => (
                              <tr key={idx} className="border-b">
                                {Object.values(row).map((value: any, vidx) => (
                                  <td key={vidx} className="px-3 py-2 text-xs">
                                    {typeof value === 'number' && value > 100 
                                      ? value.toLocaleString() 
                                      : value}
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