import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { Login } from './components/auth/Login';
import { Register } from './components/auth/Register';
import { ChatLayout } from './components/chat/ChatLayout';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { ConnectionDetailPage } from './pages/ConnectionDetailPage';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

// Wrapper components to provide navigation props
const LoginPage = () => {
  const navigate = useNavigate();
  return <Login onSwitchToRegister={() => navigate('/register')} />;
};

const RegisterPage = () => {
  const navigate = useNavigate();
  return <Register onSwitchToLogin={() => navigate('/login')} />;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          
          {/* Protected routes */}
          <Route path="/" element={
            <ProtectedRoute>
              <ChatLayout />
            </ProtectedRoute>
          } />
          
          <Route path="/connections" element={
            <ProtectedRoute>
              <ConnectionsPage />
            </ProtectedRoute>
          } />
          
          <Route path="/connections/:id" element={
            <ProtectedRoute>
              <ConnectionDetailPage />
            </ProtectedRoute>
          } />
          
          {/* Redirect any unknown routes to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;