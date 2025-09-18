import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import "./App.css";
import axios from "axios";

// Normalize and set backend URL
const RAW_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const BACKEND_URL = RAW_BACKEND_URL.replace(/\/$/, ""); // remove trailing slash if present
const API = `${BACKEND_URL}/api`;

// Set up axios defaults (baseURL + headers)
axios.defaults.baseURL = BACKEND_URL; // use root; always call URLs as /api/...
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Separate Authentication Component to prevent re-renders
const AuthForm = ({ authMode, onSubmit, onToggleMode, onBackToHome }) => {
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });

  const handleInputChange = useCallback((field) => (e) => {
    setFormData(prev => ({
      ...prev,
      [field]: e.target.value
    }));
  }, []);

  const handleSubmit = useCallback((e) => {
    e.preventDefault();
    onSubmit(formData);
  }, [formData, onSubmit]);

  const toggleMode = useCallback(() => {
    setFormData({ name: '', email: '', password: '' });
    onToggleMode();
  }, [onToggleMode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-lg w-full max-w-md">
        <h2 className="text-2xl font-bold text-center mb-6">
          {authMode === 'login' ? 'Login' : 'Register'}
        </h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {authMode === 'register' && (
            <input
              type="text"
              placeholder="Full Name"
              value={formData.name}
              onChange={handleInputChange('name')}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              required
              autoComplete="name"
            />
          )}
          
          <input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={handleInputChange('email')}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            required
            autoComplete="email"
          />
          
          <input
            type="password"
            placeholder="Password"
            value={formData.password}
            onChange={handleInputChange('password')}
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            required
            autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
          />
          
          {authMode === 'register' && (
            <p className="text-sm text-gray-500">
              Password must have 8+ characters with uppercase, lowercase, and numbers
            </p>
          )}
          
          <button
            type="submit"
            className="w-full bg-indigo-600 text-white p-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
          >
            {authMode === 'login' ? 'Login' : 'Register'}
          </button>
        </form>
        
        <p className="text-center mt-4">
          {authMode === 'login' ? "Don't have an account? " : "Already have an account? "}
          <button
            onClick={toggleMode}
            className="text-indigo-600 font-semibold hover:underline"
          >
            {authMode === 'login' ? 'Register' : 'Login'}
          </button>
        </p>
        
        <button
          onClick={onBackToHome}
          className="mt-4 text-gray-500 hover:text-gray-700"
        >
          ← Back to Home
        </button>
      </div>
    </div>
  );
};

// Enhanced Webcam Component for Eye Capture
const WebcamCapture = ({ onCapture, onClose }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  const startCamera = async () => {
    try {
      setError(null);
      
      // Stop any existing camera first
      stopCamera();
      
      // Wait a bit to ensure cleanup is complete
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Check if getUserMedia is supported
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera access not supported in this browser');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user'
        }
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        
        // Handle the play promise properly to avoid interruption errors
        const playPromise = videoRef.current.play();
        
        if (playPromise !== undefined) {
          try {
            await playPromise;
            setIsStreaming(true);
            setError(null);
          } catch (playError) {
            console.error('Video play error:', playError);
            // Don't throw here, video might still work
            setIsStreaming(true);
          }
        } else {
          setIsStreaming(true);
        }
      }
    } catch (err) {
      console.error('Error accessing camera:', err);
      
      let errorMessage = 'No se pudo acceder a la cámara. ';
      
      if (err.name === 'NotAllowedError') {
        errorMessage += 'Por favor permite el acceso a la cámara en tu navegador y recarga la página.';
      } else if (err.name === 'NotFoundError') {
        errorMessage += 'No se encontró ninguna cámara conectada.';
      } else if (err.name === 'NotSupportedError') {
        errorMessage += 'Tu navegador no soporta acceso a la cámara.';
      } else if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
        errorMessage += 'Se requiere conexión HTTPS para acceder a la cámara.';
      } else {
        errorMessage += 'Error desconocido. Verifica que ninguna otra aplicación esté usando la cámara.';
      }
      
      setError(errorMessage);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
      videoRef.current.srcObject = null;
      // Pause video to prevent play() conflicts
      videoRef.current.pause();
    }
    setIsStreaming(false);
  };

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    setIsCapturing(true);
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw video frame to canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to blob
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], 'eye-capture.jpg', { type: 'image/jpeg' });
        onCapture(file);
        stopCamera();
        onClose();
      }
      setIsCapturing(false);
    }, 'image/jpeg', 0.9);
  }, [onCapture, onClose]);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded-lg max-w-2xl w-full mx-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold">Captura de Imagen del Ojo</h3>
          <button
            onClick={() => {
              stopCamera();
              onClose();
            }}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        {error ? (
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={startCamera}
              className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
            >
              Intentar de nuevo
            </button>
          </div>
        ) : (
          <div className="text-center">
            <div className="relative mb-4">
              <video
                ref={videoRef}
                className="w-full max-w-md mx-auto rounded-lg shadow-lg"
                autoPlay
                playsInline
                muted
              />
              <canvas ref={canvasRef} className="hidden" />
              
              {/* Overlay guide for eye positioning */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="border-2 border-indigo-400 border-dashed rounded-full w-32 h-32 flex items-center justify-center">
                  <span className="text-indigo-600 text-sm font-medium bg-white bg-opacity-75 px-2 py-1 rounded">
                    Posiciona tu ojo aquí
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
                <p className="font-medium mb-1">📋 Instrucciones:</p>
                <ul className="text-left space-y-1">
                  <li>• Mantén el ojo abierto y bien iluminado</li>
                  <li>• Centra el ojo en el círculo guía</li>
                  <li>• Mantén la cámara estable</li>
                  <li>• Evita parpadear al tomar la foto</li>
                </ul>
              </div>

              <div className="flex space-x-4 justify-center">
                <button
                  onClick={capturePhoto}
                  disabled={!isStreaming || isCapturing}
                  className="bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center space-x-2"
                >
                  {isCapturing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Capturando...</span>
                    </>
                  ) : (
                    <>
                      <span>📸</span>
                      <span>Tomar Foto</span>
                    </>
                  )}
                </button>
                
                <button
                  onClick={() => {
                    stopCamera();
                    onClose();
                  }}
                  className="bg-gray-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-gray-600"
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const VisionCareApp = () => {
  const [user, setUser] = useState(null);
  const [currentView, setCurrentView] = useState('home');
  const [authMode, setAuthMode] = useState('login');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [showWebcam, setShowWebcam] = useState(false);
  const [captureMode, setCaptureMode] = useState('upload'); // 'upload' or 'webcam'

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUserInfo();
    }
  }, []);

  const fetchUserInfo = useCallback(async () => {
    try {
  const response = await axios.get(`/api/auth/profile/`);
      setUser(response.data);
    } catch (error) {
      console.error('Error fetching user info:', error);
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
    }
  }, []);

  const handleAuth = useCallback(async (formData) => {
    try {
      if (authMode === 'register') {
        // Django expects separate first_name and last_name
        const name = (formData.name || '').trim();
        const [firstName, ...lastNameParts] = name.split(/\s+/);
        // Ensure last_name is not blank (model requires non-empty)
        const lastName = (lastNameParts.join(' ') || firstName || 'User').trim();
        
        const registerData = {
          email: formData.email,
          username: formData.email, // Use email as username
          first_name: firstName,
          last_name: lastName,
          password: formData.password,
          password_confirm: formData.password
        };
        
  const response = await axios.post(`/api/auth/register/`, registerData);
        
        // Django returns tokens immediately on registration
        if (response.data.tokens) {
          const token = response.data.tokens.access;
          localStorage.setItem('token', token);
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          setUser(response.data.user);
          setCurrentView('dashboard');
        } else {
          alert('Registration successful! Please login.');
          setAuthMode('login');
        }
      } else {
        const response = await axios.post(`/api/auth/login/`, {
          email: formData.email,
          password: formData.password
        });
        
        const token = response.data.tokens.access;
        localStorage.setItem('token', token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        setUser(response.data.user);
        setCurrentView('dashboard');
      }
    } catch (error) {
      // Surface the most helpful message possible from backend or network
      const data = error.response?.data;
      const status = error.response?.status;
  const networkMsg = !error.response ? `No se pudo conectar con el servidor (${error.message}). Verifica que el backend esté corriendo en ${API}.` : null;

      // Try to extract the first field-level error if present (e.g., last_name, username, etc.)
      let fieldMsg = null;
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        const firstArray = Object.values(data).find(v => Array.isArray(v) && v.length > 0);
        if (Array.isArray(firstArray)) fieldMsg = firstArray[0];
      }

      const errorMessage =
        networkMsg ||
        data?.detail ||
        data?.message ||
        (Array.isArray(data?.non_field_errors) && data.non_field_errors[0]) ||
        data?.email?.[0] ||
        data?.password?.[0] ||
        fieldMsg ||
        (status === 400 ? 'Datos inválidos. Revisa el correo y la contraseña.' : 'Authentication failed');

      alert(errorMessage);
    }
  }, [authMode]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
    setCurrentView('home');
    setAnalysisResult(null);
    setAnalysisHistory([]);
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files[0];
    if (file) {
      processSelectedFile(file);
    }
  }, []);

  const processSelectedFile = useCallback((file) => {
    if (file.size > 5 * 1024 * 1024) {
      alert('File size must be less than 5MB');
      return;
    }
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }
    
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
  }, []);

  const handleWebcamCapture = useCallback((file) => {
    processSelectedFile(file);
    setShowWebcam(false);
    setCaptureMode('webcam');
  }, [processSelectedFile]);

  const analyzeImage = useCallback(async () => {
    if (!selectedFile) {
      alert('Please select an image first');
      return;
    }

    setIsAnalyzing(true);
    const formData = new FormData();
    formData.append('image', selectedFile); // Django expects 'image' field

    try {
  const response = await axios.post(`/api/analyze-image/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setAnalysisResult(response.data.analysis); // Django returns nested analysis object
      setCurrentView('results');
      loadAnalysisHistory();
    } catch (error) {
      const errorMessage = error.response?.data?.error || 
                          error.response?.data?.detail || 
                          'Analysis failed';
      alert(errorMessage);
    } finally {
      setIsAnalyzing(false);
    }
  }, [selectedFile]);

  const loadAnalysisHistory = useCallback(async () => {
    try {
  const response = await axios.get(`/api/history/`);
      setAnalysisHistory(response.data);
    } catch (error) {
      console.error('Error loading history:', error);
    }
  }, []);

  const downloadAnalysisPDF = useCallback(async (analysisId) => {
    try {
  const response = await axios.get(`/api/download-analysis/${analysisId}/`, {
        responseType: 'blob'
      });
      
      // Create blob URL and download
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Get filename from headers or use default
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'VisionCare_Analisis.pdf';
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      alert('Error descargando el PDF: ' + (error.response?.data?.detail || error.message));
    }
  }, []);

  const getDiagnosisColor = useCallback((diagnosis) => {
    switch (diagnosis.toLowerCase()) {
      case 'normal': return 'text-green-600';
      case 'cataracts': return 'text-orange-600';
      case 'conjunctivitis': return 'text-red-600';
      case 'multiple conditions': return 'text-purple-600';
      default: return 'text-gray-600';
    }
  }, []);

  const getDiagnosisIcon = useCallback((diagnosis) => {
    switch (diagnosis.toLowerCase()) {
      case 'normal': return '✅';
      case 'cataracts': return '🔍';
      case 'conjunctivitis': return '🔴';
      case 'multiple conditions': return '⚠️';
      default: return '❓';
    }
  }, []);

  // Memoized components to prevent unnecessary re-renders
  const HomePage = useMemo(() => () => (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-4">
            <img
              src="/hero-visioncare.png"
              alt="VisionCare Web"
              className="max-w-full w-[262px] md:w-[362px] h-auto object-contain"
              loading="lazy"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          </div>
          <h1 className="sr-only">VisionCare Web</h1>
          <p className="text-xl text-gray-600 mb-8">
            AI-Powered Eye Disease Detection System
          </p>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">
            Advanced detection of cataracts and conjunctivitis using artificial intelligence
            and computer vision technology. Get instant analysis of your eye health.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mb-12">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">🔍</div>
            <h3 className="text-xl font-semibold mb-2">Advanced AI Analysis</h3>
            <p className="text-gray-600">
              Our AI uses OpenCV and machine learning to detect cataracts and conjunctivitis
              with high accuracy.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">📱</div>
            <h3 className="text-xl font-semibold mb-2">Easy Image Upload</h3>
            <p className="text-gray-600">
              Simply upload a clear photo of your eye and get instant analysis results
              with detailed recommendations.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">📊</div>
            <h3 className="text-xl font-semibold mb-2">Track Progress</h3>
            <p className="text-gray-600">
              Keep track of your eye health over time with detailed history and
              comparison features.
            </p>
          </div>
        </div>

        <div className="text-center">
          <button
            onClick={() => setCurrentView('auth')}
            className="bg-indigo-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-indigo-700 transition-colors"
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  ), []);

  // Dashboard Page
  const DashboardPage = useMemo(() => () => (
    <div className="min-h-screen bg-gray-50">
      {showWebcam && (
        <WebcamCapture
          onCapture={handleWebcamCapture}
          onClose={() => setShowWebcam(false)}
        />
      )}
      
      <nav className="bg-white shadow-sm p-4">
        <div className="container mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <img
              src="/logo.svg"
              alt="Logo VisionCare Web"
              className="h-8 w-8 object-contain"
              loading="lazy"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
            <h1 className="text-2xl font-bold text-indigo-800">VisionCare Web</h1>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-gray-600">Welcome, {user?.first_name || user?.name}</span>
            <button
              onClick={() => {
                setCurrentView('history');
                loadAnalysisHistory();
              }}
              className="text-indigo-600 hover:text-indigo-800"
            >
              History
            </button>
            <button
              onClick={handleLogout}
              className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-3xl font-bold text-center mb-8">Eye Disease Analysis</h2>
            
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-xl font-semibold mb-4">Capture Eye Image</h3>
                
                {/* Image capture options */}
                <div className="mb-6">
                  <div className="flex space-x-4 mb-4">
                    <button
                      onClick={() => setCaptureMode('upload')}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        captureMode === 'upload'
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      📁 Upload Image
                    </button>
                    <button
                      onClick={() => setCaptureMode('webcam')}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        captureMode === 'webcam'
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      📷 Use Webcam
                    </button>
                  </div>
                </div>

                {captureMode === 'upload' ? (
                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileSelect}
                      className="hidden"
                      id="fileInput"
                    />
                    <label
                      htmlFor="fileInput"
                      className="cursor-pointer block"
                    >
                      {previewUrl ? (
                        <img
                          src={previewUrl}
                          alt="Preview"
                          className="max-w-full max-h-64 mx-auto rounded-lg"
                        />
                      ) : (
                        <div>
                          <div className="text-4xl mb-2">📁</div>
                          <p className="text-gray-500">Click to select an image</p>
                          <p className="text-sm text-gray-400 mt-2">
                            JPG, PNG up to 5MB
                          </p>
                        </div>
                      )}
                    </label>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-indigo-300 rounded-lg p-6 text-center bg-indigo-50">
                    {previewUrl ? (
                      <div>
                        <img
                          src={previewUrl}
                          alt="Captured"
                          className="max-w-full max-h-64 mx-auto rounded-lg mb-4"
                        />
                        <p className="text-sm text-gray-600 mb-4">✅ Image captured successfully</p>
                        <button
                          onClick={() => setShowWebcam(true)}
                          className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
                        >
                          📷 Capture New Photo
                        </button>
                      </div>
                    ) : (
                      <div>
                        <div className="text-4xl mb-2">📷</div>
                        <p className="text-gray-700 font-medium mb-2">Webcam Capture</p>
                        <p className="text-sm text-gray-600 mb-4">
                          Take a photo directly with your camera
                        </p>
                        <button
                          onClick={() => setShowWebcam(true)}
                          className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
                        >
                          📷 Open Camera
                        </button>
                      </div>
                    )}
                  </div>
                )}
                
                <button
                  onClick={analyzeImage}
                  disabled={!selectedFile || isAnalyzing}
                  className="w-full mt-4 bg-green-600 text-white p-3 rounded-lg font-semibold hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {isAnalyzing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <span>🔍</span>
                      <span>Analyze Eye Image</span>
                    </>
                  )}
                </button>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-4">How it works</h3>
                <div className="space-y-4">
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-600 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                      1
                    </div>
                    <div>
                      <h4 className="font-semibold">Image Capture</h4>
                      <p className="text-gray-600 text-sm">
                        Upload an image or use webcam to capture a clear photo of your eye
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-600 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                      2
                    </div>
                    <div>
                      <h4 className="font-semibold">Advanced Processing</h4>
                      <p className="text-gray-600 text-sm">
                        OpenCV algorithms enhance image quality and detect eye regions
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-600 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                      3
                    </div>
                    <div>
                      <h4 className="font-semibold">AI Medical Analysis</h4>
                      <p className="text-gray-600 text-sm">
                        Advanced AI models analyze for cataracts and conjunctivitis
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-600 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                      4
                    </div>
                    <div>
                      <h4 className="font-semibold">Medical Report</h4>
                      <p className="text-gray-600 text-sm">
                        Get detailed diagnosis with confidence scores and medical recommendations
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-800 mb-2">📋 Best Practices</h4>
                  <ul className="text-sm text-yellow-700 space-y-1">
                    <li>• Ensure good lighting on your eye</li>
                    <li>• Keep the eye wide open</li>
                    <li>• Hold camera steady and close</li>
                    <li>• Avoid reflections or shadows</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  ), [user, previewUrl, selectedFile, isAnalyzing, captureMode, showWebcam, handleFileSelect, analyzeImage, handleLogout, loadAnalysisHistory, handleWebcamCapture]);

  // Results Page
  const ResultsPage = useMemo(() => () => (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm p-4">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold text-indigo-800">VisionCare Web</h1>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setCurrentView('dashboard')}
              className="text-indigo-600 hover:text-indigo-800"
            >
              New Analysis
            </button>
            <button
              onClick={() => {
                setCurrentView('history');
                loadAnalysisHistory();
              }}
              className="text-indigo-600 hover:text-indigo-800"
            >
              History
            </button>
            <button
              onClick={handleLogout}
              className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h2 className="text-3xl font-bold text-center mb-8">Analysis Results</h2>
            
            {analysisResult && (
              <div className="grid md:grid-cols-2 gap-8">
                <div>
                  <h3 className="text-xl font-semibold mb-4">Processed Image</h3>
                  {analysisResult.image_url ? (
                    <img
                      src={analysisResult.image_url}
                      alt="Analyzed eye"
                      className="w-full rounded-lg shadow-md"
                    />
                  ) : (
                    <div className="w-full h-64 bg-gray-200 rounded-lg flex items-center justify-center">
                      <span className="text-gray-500">Image not available</span>
                    </div>
                  )}
                </div>
                
                <div>
                  <h3 className="text-xl font-semibold mb-4">Diagnosis</h3>
                  <div className="bg-gray-50 p-6 rounded-lg">
                    <div className="flex items-center mb-4">
                      <span className="text-3xl mr-3">{getDiagnosisIcon(analysisResult.diagnosis)}</span>
                      <div>
                        <h4 className={`text-2xl font-bold ${getDiagnosisColor(analysisResult.diagnosis)}`}>
                          {analysisResult.diagnosis}
                        </h4>
                        <p className="text-gray-600">
                          Confidence: {(analysisResult.confidence_score * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                    
                    <div className="space-y-3">
                      {analysisResult.ai_analysis_text && (
                        <div>
                          <h5 className="font-semibold">AI Analysis:</h5>
                          <p className="text-gray-600">{analysisResult.ai_analysis_text}</p>
                        </div>
                      )}
                      
                      {analysisResult.recommendations && (
                        <div>
                          <h5 className="font-semibold">Recommendations:</h5>
                          <p className="text-gray-600">{analysisResult.recommendations}</p>
                        </div>
                      )}

                      {analysisResult.medical_advice && (
                        <div>
                          <h5 className="font-semibold">Medical Advice:</h5>
                          <p className="text-gray-600">{analysisResult.medical_advice}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="mt-6">
                    <h4 className="font-semibold mb-3">Analysis Details</h4>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span>OpenCV Redness Score:</span>
                        <span className="font-semibold">{(analysisResult.opencv_redness_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>OpenCV Opacity Score:</span>
                        <span className="font-semibold">{(analysisResult.opencv_opacity_score * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>AI Confidence:</span>
                        <span className="font-semibold">{(analysisResult.ai_confidence * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Severity:</span>
                        <span className="font-semibold capitalize">{analysisResult.severity}</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* PDF Download Button */}
                  <div className="mt-6">
                    <button
                      onClick={() => downloadAnalysisPDF(analysisResult.id)}
                      className="w-full bg-red-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
                    >
                      <span>📄</span>
                      <span>Descargar Reporte PDF</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ), [analysisResult, getDiagnosisIcon, getDiagnosisColor, handleLogout, loadAnalysisHistory, downloadAnalysisPDF]);

  // History Page
  const HistoryPage = useMemo(() => () => (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm p-4">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold text-indigo-800">VisionCare Web</h1>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setCurrentView('dashboard')}
              className="text-indigo-600 hover:text-indigo-800"
            >
              New Analysis
            </button>
            <button
              onClick={handleLogout}
              className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold mb-8">Analysis History</h2>
          
          {analysisHistory.length === 0 ? (
            <div className="bg-white rounded-lg shadow-lg p-8 text-center">
              <p className="text-gray-500 text-lg">No analysis history found</p>
              <button
                onClick={() => setCurrentView('dashboard')}
                className="mt-4 bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700"
              >
                Start Your First Analysis
              </button>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {analysisHistory.map((analysis, index) => (
                <div key={analysis.id} className="bg-white rounded-lg shadow-lg p-6">
                  {analysis.image_url ? (
                    <img
                      src={analysis.image_url}
                      alt="Analysis thumbnail"
                      className="w-full h-32 object-cover rounded-lg mb-4"
                    />
                  ) : (
                    <div className="w-full h-32 bg-gray-200 rounded-lg mb-4 flex items-center justify-center">
                      <span className="text-gray-400">No image</span>
                    </div>
                  )}
                  
                  <div className="flex items-center mb-2">
                    <span className="text-xl mr-2">{getDiagnosisIcon(analysis.diagnosis)}</span>
                    <h3 className={`font-bold ${getDiagnosisColor(analysis.diagnosis)}`}>
                      {analysis.diagnosis}
                    </h3>
                  </div>
                  
                  <p className="text-gray-600 text-sm mb-2">
                    Confidence: {(analysis.confidence_score * 100).toFixed(1)}%
                  </p>
                  
                  <p className="text-gray-500 text-sm mb-4">
                    {new Date(analysis.created_at).toLocaleDateString()}
                  </p>
                  
                  {/* PDF Download Button */}
                  <button
                    onClick={() => downloadAnalysisPDF(analysis.id)}
                    className="w-full bg-red-600 text-white px-4 py-2 rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
                  >
                    <span>📄</span>
                    <span>Descargar PDF</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  ), [analysisHistory, getDiagnosisIcon, getDiagnosisColor, handleLogout, downloadAnalysisPDF]);

  // Main render logic
  if (!user && currentView !== 'home' && currentView !== 'auth') {
    return <HomePage />;
  }

  switch (currentView) {
    case 'home':
      return <HomePage />;
    case 'auth':
      return (
        <AuthForm
          authMode={authMode}
          onSubmit={handleAuth}
          onToggleMode={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
          onBackToHome={() => setCurrentView('home')}
        />
      );
    case 'dashboard':
      return <DashboardPage />;
    case 'results':
      return <ResultsPage />;
    case 'history':
      return <HistoryPage />;
    default:
      return <HomePage />;
  }
};

export default VisionCareApp;