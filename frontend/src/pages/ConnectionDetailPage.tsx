import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Database, CheckCircle, AlertCircle, Clock, Zap, Play, Upload, Settings } from 'lucide-react';
import { Connection } from '../types/chat';
import { chatService } from '../services/chat';

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
  return (
    <div className="space-y-6">
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

      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Statistics</h2>
        <div className="grid grid-cols-3 gap-6">
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
              {connection.last_queried_at ? new Date(connection.last_queried_at).toLocaleDateString() : 'Never'}
            </div>
            <div className="text-sm text-gray-500">Last Queried</div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Column Descriptions Tab Component
const ColumnDescriptionsTab: React.FC<{ connection: Connection; onConnectionUpdate: (connection: Connection) => void }> = ({ connection, onConnectionUpdate }) => {
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<Array<{column: string; description: string}>>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load existing column descriptions if any
    loadColumnDescriptions();
  }, []);

  const loadColumnDescriptions = async () => {
    try {
      // Mock API call - replace with real endpoint
      const response = await fetch(`http://localhost:6020/connections/${connection.id}/column-descriptions`);
      if (response.ok) {
        const data = await response.json();
        setCsvData(data.descriptions || []);
      }
    } catch (error) {
      console.log('No existing column descriptions found');
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
      // Mock API call - replace with real endpoint
      const formData = new FormData();
      formData.append('file', csvFile);

      const response = await fetch(`http://localhost:6020/connections/${connection.id}/column-descriptions`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      // Update connection status
      onConnectionUpdate({
        ...connection,
        column_descriptions_uploaded: true
      });

      alert('Column descriptions uploaded successfully!');
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

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Column Descriptions</h2>
          {connection.column_descriptions_uploaded && (
            <div className="flex items-center gap-2 text-green-600 text-sm">
              <CheckCircle size={16} />
              <span>Descriptions uploaded</span>
            </div>
          )}
        </div>
        
        <p className="text-gray-600 mb-6">
          Upload a CSV file with column descriptions to improve AI query accuracy. 
          The CSV should have two columns: <strong>column</strong> and <strong>description</strong>.
        </p>

        {/* File Upload Area */}
        <div className="mb-6">
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
          <div>
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
        {csvData.length === 0 && (
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
const SchemaTab: React.FC<{ connection: Connection }> = ({ connection }) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Table Schema</h2>
        <p className="text-gray-600 mb-4">
          Schema information and column descriptions for <strong>{connection.table_name}</strong>
        </p>
        
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-blue-800 text-sm">
            🚧 Schema management features coming soon! This will include:
          </p>
          <ul className="text-blue-700 text-sm mt-2 space-y-1">
            <li>• Column descriptions and data types</li>
            <li>• Sample data preview</li>
            <li>• CSV upload for column descriptions</li>
            <li>• Data profiling and statistics</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

// Training Data Tab Component
const TrainingDataTab: React.FC<{ connection: Connection }> = ({ connection }) => {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Training Examples</h2>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            Generate Examples
          </button>
        </div>
        
        <p className="text-gray-600 mb-4">
          Generated question-SQL pairs for training the AI model
        </p>
        
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800 text-sm">
            🚧 Training data management features coming soon! This will include:
          </p>
          <ul className="text-yellow-700 text-sm mt-2 space-y-1">
            <li>• View generated question-SQL examples</li>
            <li>• Edit and improve training pairs</li>
            <li>• Add custom examples</li>
            <li>• Delete poor quality examples</li>
            <li>• Training data quality metrics</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

// Training Tab Component
const TrainingTab: React.FC<{ connection: Connection; onConnectionUpdate: (connection: Connection) => void }> = ({ connection, onConnectionUpdate }) => {
  const [training, setTraining] = useState(false);

  const handleStartTraining = async () => {
    setTraining(true);
    // Mock training process
    setTimeout(() => {
      setTraining(false);
      onConnectionUpdate({ ...connection, status: 'trained' });
    }, 3000);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Model Training</h2>
        
        {connection.status === 'trained' ? (
          <div className="text-center py-8">
            <CheckCircle size={48} className="mx-auto text-green-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Model Trained Successfully!</h3>
            <p className="text-gray-600 mb-6">
              Your AI model is ready to answer questions about your data.
            </p>
            <button
              onClick={handleStartTraining}
              disabled={training}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              Retrain Model
            </button>
          </div>
        ) : (
          <div className="text-center py-8">
            <Zap size={48} className="mx-auto text-yellow-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Ready to Train Model</h3>
            <p className="text-gray-600 mb-6">
              Train the AI model on your database schema and examples to enable natural language queries.
            </p>
            <button
              onClick={handleStartTraining}
              disabled={training}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {training ? 'Training...' : 'Start Training'}
            </button>
          </div>
        )}
        
        {training && (
          <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-blue-800 mb-2">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="font-medium">Training in progress...</span>
            </div>
            <p className="text-blue-700 text-sm">
              This may take a few minutes. The model is learning your database structure and training examples.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};