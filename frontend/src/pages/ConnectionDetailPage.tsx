import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Database, CheckCircle, AlertCircle, Clock, Zap, Play, Upload, Settings } from 'lucide-react';
import { Connection } from '../types/chat';
import { chatService } from '../services/chat';
import { sseConnection } from '../services/sse';



type TabType = 'details' | 'schema' | 'column-descriptions' | 'training-data' | 'training';

export const ConnectionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  console.log('ConnectionDetailPage rendering, id from params:', id);
  
  const [activeTab, setActiveTab] = useState<TabType>('details');
  const [connection, setConnection] = useState<Connection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log('ConnectionDetailPage mounted, ID:', id);
    if (id) {
      loadConnection();
    } else {
      console.error('No ID provided in URL params');
      setError('No connection ID provided');
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
  // Listen for tab change events from Details tab
  const handleTabChange = (event: any) => {
    setActiveTab(event.detail as TabType);
  };

  document.addEventListener('changeTab', handleTabChange);
  
  return () => {
    document.removeEventListener('changeTab', handleTabChange);
  };
}, []);


  const loadConnection = async () => {
    try {
      console.log('Loading connection with ID:', id);
      const response = await fetch(`http://localhost:6020/connections/${id}`);
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error('Connection not found');
      }
      
      const connectionData = await response.json();
      console.log('Connection data loaded:', connectionData);
      setConnection(connectionData);
    } catch (err: any) {
      console.error('Failed to load connection:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'trained':
        return { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', text: 'Trained' };
      case 'training':
        return { icon: Zap, color: 'text-yellow-600', bg: 'bg-yellow-100', text: 'Training' };
      case 'data_generated':
        return { icon: Play, color: 'text-blue-600', bg: 'bg-blue-100', text: 'Ready to Train' };
      case 'test_success':
        return { icon: CheckCircle, color: 'text-blue-600', bg: 'bg-blue-100', text: 'Connected' };
      case 'generating_data':
        return { icon: Clock, color: 'text-yellow-600', bg: 'bg-yellow-100', text: 'Generating Data' };
      default:
        return { icon: AlertCircle, color: 'text-gray-600', bg: 'bg-gray-100', text: 'Unknown' };
    }
  };

  const tabs = [
    { id: 'details', label: 'Details', icon: Database, description: 'Connection information and settings' },
    { id: 'schema', label: 'Schema', icon: Settings, description: 'Table structure and column information' },
    { id: 'column-descriptions', label: 'Column Descriptions', icon: Upload, description: 'Upload and manage column descriptions' },
    { id: 'training-data', label: 'Training Data', icon: Play, description: 'Generated examples and training pairs' },
    { id: 'training', label: 'Training', icon: Zap, description: 'Train and manage AI model' }
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading connection...</p>
        </div>
      </div>
    );
  }

  if (error || !connection) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle size={48} className="mx-auto text-red-500 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Connection Not Found</h2>
          <p className="text-gray-600 mb-4">{error || 'The requested connection could not be found.'}</p>
          <button
            onClick={() => navigate('/connections')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Back to Connections
          </button>
        </div>
      </div>
    );
  }

  const statusInfo = getStatusInfo(connection.status);
  const StatusIcon = statusInfo.icon;

  const renderTabContent = () => {
    switch (activeTab) {
      case 'details':
        return <DetailsTab connection={connection} onConnectionUpdate={setConnection} />;
      case 'schema':
        return <SchemaTab connection={connection} />;
      case 'column-descriptions':
        return <ColumnDescriptionsTab connection={connection} onConnectionUpdate={setConnection} />;
      case 'training-data':
        return <TrainingDataTab connection={connection} />;
      case 'training':
        return <TrainingTab connection={connection} onConnectionUpdate={setConnection} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/connections')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft size={20} className="text-gray-600" />
              </button>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Database size={20} className="text-blue-600" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-gray-900">{connection.name}</h1>
                  <p className="text-sm text-gray-500">{connection.server} • {connection.database_name}</p>
                </div>
              </div>
            </div>
            
            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm ${statusInfo.bg} ${statusInfo.color}`}>
              <StatusIcon size={16} />
              <span className="font-medium">{statusInfo.text}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            {tabs.map(tab => {
              const TabIcon = tab.icon;
              const isActive = activeTab === tab.id;
              
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    isActive
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <TabIcon size={16} />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {renderTabContent()}
      </div>
    </div>
  );
};

// Details Tab Component
const DetailsTab: React.FC<{ connection: Connection; onConnectionUpdate: (connection: Connection) => void }> = ({ connection, onConnectionUpdate }) => {
  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'trained':
        return { 
          color: 'text-green-600', 
          bg: 'bg-green-100', 
          text: 'Model is trained and ready for queries',
          icon: CheckCircle
        };
      case 'data_generated':
        return { 
          color: 'text-blue-600', 
          bg: 'bg-blue-100', 
          text: 'Training data generated',
          icon: Play
        };
      case 'test_success':
        return { 
          color: 'text-green-600', 
          bg: 'bg-green-100', 
          text: 'Connection successful and ready to use',
          icon: CheckCircle
        };
      case 'training':
        return { 
          color: 'text-purple-600', 
          bg: 'bg-purple-100', 
          text: 'Model training in progress',
          icon: Clock
        };
      case 'generating_data':
        return { 
          color: 'text-blue-600', 
          bg: 'bg-blue-100', 
          text: 'Generating training examples',
          icon: Clock
        };
      default:
        return { 
          color: 'text-gray-600', 
          bg: 'bg-gray-100', 
          text: 'Unknown status',
          icon: AlertCircle
        };
    }
  };

  const statusInfo = getStatusInfo(connection.status);
  const StatusIcon = statusInfo.icon;

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Connection Status</h2>
        <div className={`flex items-center gap-3 p-4 rounded-lg ${statusInfo.bg}`}>
          <StatusIcon size={24} className={statusInfo.color} />
          <div>
            <div className={`font-medium ${statusInfo.color}`}>
              {connection.status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </div>
            <div className={`text-sm ${statusInfo.color.replace('600', '700')}`}>
              {statusInfo.text}
            </div>
          </div>
        </div>
      </div>

      {/* Connection Information */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Connection Information</h2>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Connection Name</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">{connection.name}</div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Server</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">{connection.server}</div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Database</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">{connection.database_name}</div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Table</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">{connection.table_name}</div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Driver</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">{connection.driver}</div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Created</label>
            <div className="p-3 bg-gray-50 rounded-lg text-gray-900">
              {new Date(connection.created_at).toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Usage Statistics</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{connection.total_queries}</div>
            <div className="text-sm text-gray-500">Total Queries</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{connection.generated_examples_count}</div>
            <div className="text-sm text-gray-500">Training Examples</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {connection.column_descriptions_uploaded ? 'Yes' : 'No'}
            </div>
            <div className="text-sm text-gray-500">Column Descriptions</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">
              {connection.last_queried_at ? new Date(connection.last_queried_at).toLocaleDateString() : 'Never'}
            </div>
            <div className="text-sm text-gray-500">Last Queried</div>
          </div>
        </div>
      </div>

      {/* Training Timeline */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Training Timeline</h2>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle size={16} className="text-green-600" />
            </div>
            <div className="flex-1">
              <div className="font-medium text-gray-900">Connection Created</div>
              <div className="text-sm text-gray-500">
                {new Date(connection.created_at).toLocaleString()}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              connection.generated_examples_count > 0 
                ? 'bg-green-100' 
                : 'bg-gray-100'
            }`}>
              {connection.generated_examples_count > 0 ? (
                <CheckCircle size={16} className="text-green-600" />
              ) : (
                <Clock size={16} className="text-gray-400" />
              )}
            </div>
            <div className="flex-1">
              <div className={`font-medium ${
                connection.generated_examples_count > 0 ? 'text-gray-900' : 'text-gray-500'
              }`}>
                Training Data Generated (Optional)
              </div>
              <div className="text-sm text-gray-500">
                {connection.generated_examples_count > 0 
                  ? `${connection.generated_examples_count} examples created`
                  : 'Can train with schema only'
                }
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
              connection.status === 'trained' 
                ? 'bg-green-100' 
                : 'bg-gray-100'
            }`}>
              {connection.status === 'trained' ? (
                <CheckCircle size={16} className="text-green-600" />
              ) : (
                <Clock size={16} className="text-gray-400" />
              )}
            </div>
            <div className="flex-1">
              <div className={`font-medium ${
                connection.status === 'trained' ? 'text-gray-900' : 'text-gray-500'
              }`}>
                Model Training Completed
              </div>
              <div className="text-sm text-gray-500">
                {connection.trained_at 
                  ? new Date(connection.trained_at).toLocaleString()
                  : 'Ready to train'
                }
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Column Descriptions Tab Component
// Updated Column Descriptions Tab Component - replace the existing ColumnDescriptionsTab

const ColumnDescriptionsTab: React.FC<{ connection: Connection; onConnectionUpdate: (connection: Connection) => void }> = ({ connection, onConnectionUpdate }) => {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<Array<{column: string; description: string}>>([]);
  const [columnDescriptions, setColumnDescriptions] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadColumnDescriptions();
  }, [connection.id]);

  const loadColumnDescriptions = async () => {
    try {
      setError(null);
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/column-descriptions`);
      
      if (response.ok) {
        const data = await response.json();
        setColumnDescriptions(data.column_descriptions || []);
      } else {
        console.log('No existing column descriptions found');
        setColumnDescriptions([]);
      }
    } catch (error) {
      console.error('Failed to load column descriptions:', error);
      setColumnDescriptions([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type !== 'text/csv') {
      setError('Please upload a CSV file');
      return;
    }

    setCsvFile(file);
    setError(null);
    parseCSV(file);
  };

  const parseCSV = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lines = text.trim().split('\n');
      
      if (lines.length < 2) {
        setError('CSV file must contain at least a header row and one data row');
        return;
      }

      // Parse header
      const header = lines[0].split(',').map(col => col.trim().replace(/"/g, ''));
      
      if (header.length !== 2 || header[0].toLowerCase() !== 'column' || header[1].toLowerCase() !== 'description') {
        setError('CSV must have exactly two columns: "column" and "description"');
        return;
      }

      // Parse data rows
      const data = lines.slice(1).map((line, index) => {
        const cols = line.split(',').map(col => col.trim().replace(/"/g, ''));
        if (cols.length !== 2) {
          setError(`Row ${index + 2} must have exactly 2 columns`);
          return null;
        }
        return {
          column: cols[0],
          description: cols[1]
        };
      }).filter(row => row !== null) as Array<{column: string; description: string}>;

      if (data.length === 0) {
        setError('No valid data rows found in CSV');
        return;
      }

      setCsvData(data);
      setError(null);
    };

    reader.readAsText(file);
  };

  const handleUpload = async () => {
    if (!csvFile || csvData.length === 0) return;

    setUploading(true);
    setError(null);

    try {
      // Use the mock endpoint that expects JSON data
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/column-descriptions`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          columns: csvData
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      
      // Update connection status
      onConnectionUpdate({
        ...connection,
        column_descriptions_uploaded: true
      });

      // Reload column descriptions
      await loadColumnDescriptions();

      alert(`Column descriptions uploaded successfully! Updated ${result.total_columns} columns.`);
      
      // Clear the form
      setCsvFile(null);
      setCsvData([]);
      
    } catch (error: any) {
      setError(error.message);
    } finally {
      setUploading(false);
    }
  };

  const clearFile = () => {
    setCsvFile(null);
    setCsvData([]);
    setError(null);
  };

  const downloadTemplate = () => {
    // Create a template CSV with existing columns from schema
    let csvContent = "column,description\n";
    
    if (columnDescriptions.length > 0) {
      columnDescriptions.forEach(col => {
        csvContent += `"${col.column_name}","${col.description || 'Add description here'}"\n`;
      });
    } else {
      // Default template
      csvContent += "EmployeeID,Unique identifier for each employee\n";
      csvContent += "EmployeeName,Full name of the employee\n";
      csvContent += "Department,Department where employee works\n";
      csvContent += "Salary,Annual salary in USD\n";
    }

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `${connection.name}_column_descriptions_template.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
            <span className="text-gray-600">Loading column descriptions...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Column Descriptions</h2>
          <div className="flex items-center gap-4">
            {connection.column_descriptions_uploaded && (
              <div className="flex items-center gap-2 text-green-600 text-sm">
                <CheckCircle size={16} />
                <span>Descriptions uploaded</span>
              </div>
            )}
            <button
              onClick={downloadTemplate}
              className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Download Template
            </button>
          </div>
        </div>
        
        <p className="text-gray-600 mb-6">
          Upload a CSV file with column descriptions to improve AI query accuracy. 
          The CSV should have two columns: <strong>column</strong> and <strong>description</strong>.
        </p>

        {/* Current Descriptions */}
        {columnDescriptions.length > 0 && (
          <div className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">
              Current Column Descriptions ({columnDescriptions.length} columns)
            </h3>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200 rounded-lg">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Column Name
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Data Type
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Description
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {columnDescriptions.map((col, index) => (
                    <tr key={index} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {col.column_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded font-mono">
                          {col.data_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {col.description || (
                          <span className="text-gray-400 italic">No description</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {col.has_description ? (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                            <CheckCircle size={12} />
                            Described
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-1 bg-yellow-100 text-yellow-700 text-xs rounded">
                            <AlertCircle size={12} />
                            Missing
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* File Upload Area */}
        <div className="mb-6">
          <h3 className="text-md font-medium text-gray-900 mb-3">Upload New Descriptions</h3>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
            <input
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
              id="csv-upload"
            />
            <label htmlFor="csv-upload" className="cursor-pointer block">
              <Upload size={24} className="mx-auto text-gray-400 mb-2" />
              <p className="text-sm text-gray-600">
                {csvFile ? csvFile.name : 'Click to upload CSV file or drag and drop'}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Format: column,description
              </p>
            </label>
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          {csvFile && !error && (
            <div className="mt-3 flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle size={16} />
                <span className="text-sm">File parsed successfully ({csvData.length} rows)</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:opacity-50"
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
                <button
                  onClick={clearFile}
                  className="px-3 py-1 bg-gray-500 text-white text-sm rounded hover:bg-gray-600"
                >
                  Clear
                </button>
              </div>
            </div>
          )}
        </div>

        {/* CSV Data Preview */}
        {csvData.length > 0 && (
          <div className="mb-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">
              Preview ({csvData.length} columns)
            </h3>
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-200 rounded-lg">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Column
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {csvData.map((row, index) => (
                    <tr key={index} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {row.column}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {row.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Example Format */}
        {csvData.length === 0 && columnDescriptions.length === 0 && (
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Example CSV Format:</h4>
            <pre className="text-xs text-gray-700 bg-white p-3 rounded border">
{`column,description
EmployeeID,Unique identifier for each employee
EmployeeName,Full name of the employee
Department,Department where employee works
Salary,Annual salary in USD
HireDate,Date when employee was hired`}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

// Schema Tab Component
// Updated Schema Tab Component - replace the existing SchemaTab in ConnectionDetailPage.tsx

const SchemaTab: React.FC<{ connection: Connection }> = ({ connection }) => {
  const [schemaData, setSchemaData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSchema();
  }, [connection.id]);

  const loadSchema = async () => {
    try {
      setError(null);
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/schema`);
      
      if (!response.ok) {
        if (response.status === 404) {
          setError('Schema not found. Click "Refresh Schema" to analyze the database structure.');
        } else {
          throw new Error('Failed to load schema');
        }
        setSchemaData(null);
      } else {
        const data = await response.json();
        setSchemaData(data);
      }
    } catch (err: any) {
      console.error('Failed to load schema:', err);
      setError(err.message);
      setSchemaData(null);
    } finally {
      setLoading(false);
    }
  };

  const refreshSchema = async () => {
    setRefreshing(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/refresh-schema`, {
        method: 'POST'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to refresh schema');
      }

      const result = await response.json();
      console.log('Schema refresh started:', result);
      
      // Poll for completion (in a real app, you'd use SSE)
      const pollForCompletion = async () => {
        let attempts = 0;
        const maxAttempts = 20;
        
        while (attempts < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          try {
            const schemaResponse = await fetch(`http://localhost:6020/connections/${connection.id}/schema`);
            if (schemaResponse.ok) {
              const data = await schemaResponse.json();
              setSchemaData(data);
              setRefreshing(false);
              return;
            }
          } catch (e) {
            // Continue polling
          }
          
          attempts++;
        }
        
        throw new Error('Schema refresh timed out');
      };

      await pollForCompletion();
      
    } catch (err: any) {
      console.error('Schema refresh failed:', err);
      setError(err.message);
      setRefreshing(false);
    }
  };

  const formatDataType = (dataType: string) => {
    return dataType.replace(/([a-z])([A-Z])/g, '$1 $2').toUpperCase();
  };

  const renderColumnValue = (column: any) => {
    if (column.categories && column.categories.length > 0) {
      const displayCategories = column.categories.slice(0, 5);
      const hasMore = column.categories.length > 5;
      return (
        <div>
          <div className="text-sm text-gray-600 mb-1">Categories:</div>
          <div className="flex flex-wrap gap-1">
            {displayCategories.map((cat: string, idx: number) => (
              <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                {cat}
              </span>
            ))}
            {hasMore && (
              <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                +{column.categories.length - 5} more
              </span>
            )}
          </div>
        </div>
      );
    }
    
    if (column.range) {
      return (
        <div className="text-sm text-gray-600">
          <div>Min: <span className="font-medium">{column.range.min}</span></div>
          <div>Max: <span className="font-medium">{column.range.max}</span></div>
          <div>Avg: <span className="font-medium">{column.range.avg?.toFixed(2)}</span></div>
        </div>
      );
    }
    
    if (column.date_range) {
      return (
        <div className="text-sm text-gray-600">
          <div>From: <span className="font-medium">{column.date_range.min}</span></div>
          <div>To: <span className="font-medium">{column.date_range.max}</span></div>
        </div>
      );
    }
    
    return (
      <div className="text-sm text-gray-500">
        {column.variable_range || 'No sample data'}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
            <span className="text-gray-600">Loading schema...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Table Schema</h2>
            <p className="text-gray-600">
              Structure and column information for <strong>{connection.table_name}</strong>
            </p>
          </div>
          <button
            onClick={refreshSchema}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Settings size={16} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh Schema'}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertCircle size={16} />
              <span className="font-medium">Schema Not Available</span>
            </div>
            <p className="text-yellow-700 text-sm mt-1">{error}</p>
          </div>
        )}

        {schemaData ? (
          <div className="space-y-6">
            {/* Schema Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-blue-600">
                  {schemaData.schema.table_info.total_columns}
                </div>
                <div className="text-sm text-blue-700">Total Columns</div>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-green-600">
                  {schemaData.schema.table_info.sample_rows}
                </div>
                <div className="text-sm text-green-700">Sample Rows</div>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-purple-600">
                  {schemaData.last_refreshed ? new Date(schemaData.last_refreshed).toLocaleDateString() : 'Unknown'}
                </div>
                <div className="text-sm text-purple-700">Last Refreshed</div>
              </div>
            </div>

            {/* Columns Table */}
            <div>
              <h3 className="text-md font-medium text-gray-900 mb-3">Column Information</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 rounded-lg">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                        Column Name
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                        Data Type
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                        Values/Range
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(schemaData.schema.columns).map(([columnName, columnInfo]: [string, any]) => (
                      <tr key={columnName} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">
                          {columnName}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded font-mono">
                            {formatDataType(columnInfo.data_type)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {renderColumnValue(columnInfo)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Sample Data */}
            {schemaData.schema.sample_data && schemaData.schema.sample_data.length > 0 && (
              <div>
                <h3 className="text-md font-medium text-gray-900 mb-3">Sample Data</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full border border-gray-200 rounded-lg">
                    <thead className="bg-gray-50">
                      <tr>
                        {Object.keys(schemaData.schema.sample_data[0]).map((header) => (
                          <th key={header} className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b">
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {schemaData.schema.sample_data.map((row: any, index: number) => (
                        <tr key={index} className="border-b hover:bg-gray-50">
                          {Object.values(row).map((value: any, cellIndex: number) => (
                            <td key={cellIndex} className="px-4 py-3 text-sm text-gray-700">
                              {value === null ? (
                                <span className="text-gray-400 italic">NULL</span>
                              ) : (
                                String(value)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : !loading && !error && (
          <div className="text-center py-8">
            <Database size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Schema Data</h3>
            <p className="text-gray-600 mb-4">
              Click "Refresh Schema" to analyze your database structure.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

// Training Data Tab Component
// Updated Training Data Tab Component - replace the existing TrainingDataTab

// Updated Training Data Tab Component - replace in ConnectionDetailPage.tsx

const TrainingDataTab: React.FC<{ connection: Connection }> = ({ connection }) => {
  const [trainingData, setTrainingData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [numExamples, setNumExamples] = useState(20);

  useEffect(() => {
    loadTrainingData();
  }, [connection.id, connection.generated_examples_count]);

  const loadTrainingData = async () => {
    try {
      setError(null);
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/training-data`);
      
      if (response.ok) {
        const data = await response.json();
        setTrainingData(data);
      } else if (response.status === 404) {
        setTrainingData(null);
      } else {
        throw new Error('Failed to load training data');
      }
    } catch (err: any) {
      console.error('Failed to load training data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };


  const generateExamples = async () => {
    setGenerating(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/generate-training-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          num_examples: numExamples
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start data generation');
      }

      const result = await response.json();
      console.log('Data generation started:', result);

      // Connect to SSE stream if available
      if (result.stream_url) {
        sseConnection.connect(result.stream_url, {
          onProgress: (data) => {
            console.log('Generation progress:', data);
            // Could show progress bar here
          },
          
          onCustomEvent: (eventType, data) => {
            if (eventType === 'data_generation_started') {
              console.log('Generation started:', data);
            } else if (eventType === 'example_generated') {
              console.log('New example generated:', data);
              // Could show real-time examples being generated
            }
          },
          
          onCompleted: async (data) => {
            console.log('Generation completed:', data);
            setGenerating(false);
            await loadTrainingData();
          },
          
          onError: (data) => {
            console.error('Generation failed:', data);
            setError(data.error || 'Data generation failed');
            setGenerating(false);
          }
        });
      } else {
        // Fallback: Poll for completion if no SSE
        const pollForCompletion = async () => {
          let attempts = 0;
          const maxAttempts = 30;
          
          while (attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            try {
              const trainingResponse = await fetch(`http://localhost:6020/connections/${connection.id}/training-data`);
              if (trainingResponse.ok) {
                await loadTrainingData();
                setGenerating(false);
                return;
              }
              
              const connResponse = await fetch(`http://localhost:6020/connections/${connection.id}`);
              if (connResponse.ok) {
                const connData = await connResponse.json();
                if (connData.status === 'data_generated' && connData.generated_examples_count > 0) {
                  await loadTrainingData();
                  setGenerating(false);
                  return;
                }
              }
            } catch (e) {
              console.log('Polling attempt failed, continuing...', e);
            }
            
            attempts++;
          }
          
          throw new Error('Data generation timed out');
        };

        await pollForCompletion();
      }
      
    } catch (err: any) {
      console.error('Data generation failed:', err);
      setError(err.message);
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
            <span className="text-gray-600">Loading training data...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Training Examples</h2>
            <p className="text-gray-600">
              Generated question-SQL pairs for training the AI model
            </p>
          </div>
          
          {!trainingData && (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-700">Examples:</label>
                <select
                  value={numExamples}
                  onChange={(e) => setNumExamples(parseInt(e.target.value))}
                  className="px-2 py-1 border border-gray-300 rounded text-sm"
                  disabled={generating}
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={30}>30</option>
                  <option value={50}>50</option>
                </select>
              </div>
              <button
                onClick={generateExamples}
                disabled={generating}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <Play size={16} className={generating ? 'animate-spin' : ''} />
                {generating ? 'Generating...' : 'Generate Examples'}
              </button>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle size={16} />
              <span className="font-medium">Error</span>
            </div>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
        )}

        {generating && (
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-800 mb-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="font-medium">Generating training examples...</span>
            </div>
            <p className="text-blue-700 text-sm">
              Creating {numExamples} question-SQL pairs based on your database schema. This may take a few minutes.
            </p>
          </div>
        )}

        {trainingData ? (
          <div className="space-y-6">
            {/* Training Data Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-green-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-green-600">
                  {trainingData.total_examples}
                </div>
                <div className="text-sm text-green-700">Total Examples</div>
              </div>
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-blue-600">
                  {trainingData.generated_at ? new Date(trainingData.generated_at).toLocaleDateString() : 'Unknown'}
                </div>
                <div className="text-sm text-blue-700">Generated Date</div>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="text-2xl font-bold text-purple-600">
                  {connection.status === 'trained' ? 'Trained' : 'Ready'}
                </div>
                <div className="text-sm text-purple-700">Model Status</div>
              </div>
            </div>

            {/* Regenerate Button */}
            <div className="flex justify-between items-center">
              <h3 className="text-md font-medium text-gray-900">
                Question-SQL Examples ({trainingData.total_examples})
              </h3>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <label className="text-sm text-gray-700">Examples:</label>
                  <select
                    value={numExamples}
                    onChange={(e) => setNumExamples(parseInt(e.target.value))}
                    className="px-2 py-1 border border-gray-300 rounded text-sm"
                    disabled={generating}
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={30}>30</option>
                    <option value={50}>50</option>
                  </select>
                </div>
                <button
                  onClick={generateExamples}
                  disabled={generating}
                  className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm"
                >
                  <Play size={14} />
                  Regenerate
                </button>
              </div>
            </div>

            {/* Examples List */}
            <div className="space-y-4">
              {trainingData.generated_examples.map((example: any, index: number) => (
                <div key={example.id || index} className="border border-gray-200 rounded-lg p-4">
                  <div className="mb-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded font-medium">
                        Q{index + 1}
                      </span>
                      <span className="text-sm font-medium text-gray-900">Question</span>
                    </div>
                    <p className="text-gray-700">{example.question}</p>
                  </div>
                  
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded font-medium">
                        SQL
                      </span>
                      <span className="text-sm font-medium text-gray-900">Generated Query</span>
                    </div>
                    <pre className="bg-gray-50 p-3 rounded text-sm text-gray-800 overflow-x-auto">
                      <code>{example.sql}</code>
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : !generating && (
          <div className="text-center py-8">
            <Play size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Training Data</h3>
            <p className="text-gray-600 mb-4">
              Generate training examples to prepare your AI model for natural language queries.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

// Updated Training Tab Component - replace in ConnectionDetailPage.tsx

// Fixed Training Tab Component - replace the existing TrainingTab

const TrainingTab: React.FC<{ connection: Connection; onConnectionUpdate: (connection: Connection) => void }> = ({ connection, onConnectionUpdate }) => {
  const [training, setTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);



  const handleStartTraining = async () => {
    setTraining(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/train`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start training');
      }

      const result = await response.json();
      console.log('Training started:', result);

      // Connect to SSE stream if available
      if (result.stream_url) {
        sseConnection.connect(result.stream_url, {
          onProgress: (data) => {
            console.log('Training progress:', data);
            // Could show progress percentage here
          },
          
          onCustomEvent: (eventType, data) => {
            if (eventType === 'training_started') {
              console.log('Training started:', data);
            }
          },
          
          onCompleted: async (data) => {
            console.log('Training completed:', data);
            setTraining(false);
            
            // Update connection status
            try {
              const connResponse = await fetch(`http://localhost:6020/connections/${connection.id}`);
              if (connResponse.ok) {
                const connData = await connResponse.json();
                onConnectionUpdate(connData);
              }
            } catch (e) {
              console.error('Failed to update connection:', e);
            }
          },
          
          onError: (data) => {
            console.error('Training failed:', data);
            setError(data.error || 'Training failed');
            setTraining(false);
          }
        });
      } else {
        // Fallback: Poll for completion if no SSE
        const pollForCompletion = async () => {
          let attempts = 0;
          const maxAttempts = 30;
          
          while (attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            try {
              const connResponse = await fetch(`http://localhost:6020/connections/${connection.id}`);
              if (connResponse.ok) {
                const connData = await connResponse.json();
                if (connData.status === 'trained') {
                  onConnectionUpdate(connData);
                  setTraining(false);
                  return;
                }
              }
            } catch (e) {
              // Continue polling
            }
            
            attempts++;
          }
          
          throw new Error('Training timed out');
        };

        await pollForCompletion();
      }
      
    } catch (err: any) {
      console.error('Training failed:', err);
      setError(err.message);
      setTraining(false);
    }
  };
  // Fixed logic: Can train with test_success status (no data generation required)
  const canTrain = ['test_success', 'data_generated'].includes(connection.status) || connection.status === 'trained';

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Model Training</h2>
        
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-800">
              <AlertCircle size={16} />
              <span className="font-medium">Training Error</span>
            </div>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
        )}

        {connection.status === 'trained' ? (
          <div className="text-center py-8">
            <CheckCircle size={48} className="mx-auto text-green-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Model Trained Successfully!</h3>
            <p className="text-gray-600 mb-6">
              Your AI model is ready to answer questions about your data. 
              You can now use it in the chat interface.
            </p>
            
            {/* Training Stats */}
            <div className="grid grid-cols-2 gap-4 mb-6 max-w-md mx-auto">
              <div className="bg-green-50 rounded-lg p-3">
                <div className="text-lg font-bold text-green-600">
                  {connection.generated_examples_count || 'Schema Only'}
                </div>
                <div className="text-sm text-green-700">Training Data</div>
              </div>
              <div className="bg-blue-50 rounded-lg p-3">
                <div className="text-lg font-bold text-blue-600">
                  {connection.trained_at ? new Date(connection.trained_at).toLocaleDateString() : 'Today'}
                </div>
                <div className="text-sm text-blue-700">Trained Date</div>
              </div>
            </div>
            
            <button
              onClick={handleStartTraining}
              disabled={training}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {training ? 'Retraining...' : 'Retrain Model'}
            </button>
          </div>
        ) : canTrain ? (
          <div className="text-center py-8">
            <Zap size={48} className="mx-auto text-yellow-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Ready to Train Model</h3>
            <p className="text-gray-600 mb-6">
              Train the AI model using your database schema
              {connection.generated_examples_count > 0 
                ? ` and ${connection.generated_examples_count} training examples.`
                : '. You can optionally generate training examples for better accuracy.'
              }
            </p>
            
            {/* Training Options Info */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left">
              <h4 className="font-medium text-blue-800 mb-2">Training Options:</h4>
              <ul className="text-blue-700 text-sm space-y-1">
                <li>✅ <strong>Schema-based training</strong>: Uses your table structure and column information</li>
                {connection.column_descriptions_uploaded && (
                  <li>✅ <strong>Column descriptions</strong>: Enhanced with uploaded descriptions</li>
                )}
                {connection.generated_examples_count > 0 ? (
                  <li>✅ <strong>Training examples</strong>: {connection.generated_examples_count} question-SQL pairs</li>
                ) : (
                  <li>⭕ <strong>Training examples</strong>: Optional - generate for better accuracy</li>
                )}
              </ul>
            </div>
            
            <button
              onClick={handleStartTraining}
              disabled={training}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {training ? 'Training...' : 'Start Training'}
            </button>
          </div>
        ) : (
          <div className="text-center py-8">
            <Clock size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Training Not Available</h3>
            <p className="text-gray-600 mb-4">
              Connection must be successfully tested before training can begin.
            </p>
          </div>
        )}
        
        {training && (
          <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-800 mb-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="font-medium">Training in progress...</span>
            </div>
            <p className="text-blue-700 text-sm">
              The model is learning your database structure
              {connection.generated_examples_count > 0 ? ' and training examples' : ''}
              . This may take a few minutes.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};