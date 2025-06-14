import React, { useState } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Login } from './components/auth/Login';

const AppContent: React.FC = () => {
  const { isAuthenticated, user, logout, loading } = useAuth();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [showRegister, setShowRegister] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Login 
        onSwitchToRegister={() => setShowRegister(true)} 
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold">Welcome to Tex2SQL</h1>
            <button
              onClick={logout}
              className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700"
            >
              Logout
            </button>
          </div>
          
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold">User Information</h2>
              <div className="mt-2 space-y-2">
                <p><span className="font-medium">Email:</span> {user?.email}</p>
                <p><span className="font-medium">Username:</span> {user?.username}</p>
                {user?.full_name && (
                  <p><span className="font-medium">Full Name:</span> {user.full_name}</p>
                )}
                {user?.company && (
                  <p><span className="font-medium">Company:</span> {user.company}</p>
                )}
                <p><span className="font-medium">Role:</span> {user?.role}</p>
                <p><span className="font-medium">Verified:</span> {user?.is_verified ? 'Yes' : 'No'}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;