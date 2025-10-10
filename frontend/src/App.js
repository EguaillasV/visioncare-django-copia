import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import "./App.css";
import axios from "axios";
import MetricBar from "./components/ui/MetricBar";
import Gauge from "./components/ui/Gauge";

import PhoneInput, { isValidPhoneNumber } from 'react-phone-number-input';
import flags from 'react-phone-number-input/flags';
import 'react-phone-number-input/style.css';
import './phone-input.css';
import { Country, State, City } from 'country-state-city';
import { useToast } from '@/hooks/use-toast';
// (Opcional) Si en el futuro quieres un combobox con búsqueda, podemos reintroducir react-select.

// Backend base URL: prefer env, fallback to 8001 for local dev
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:8001';
const API = `${BACKEND_URL}/api`;

// Set up axios defaults
// Nota: no fijamos Content-Type globalmente. Axios detecta JSON o FormData
// automáticamente y agrega el encabezado correcto (incluyendo el boundary en multipart).

// Ensure media URLs are absolute when backend returns relative paths
const toAbsoluteUrl = (url) => {
  if (!url) return url;
  if (typeof url !== 'string') return url;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  if (url.startsWith('/')) return `${BACKEND_URL}${url}`;
  return url;
};

// Normaliza las banderas (algunos bundlers exponen en flags.default)
const FLAG_ICONS = (flags && flags.default) ? flags.default : flags;

// Utilidad: convierte código ISO (EC, US, ES) a bandera emoji
const toEmojiFlag = (isoCode) => {
  if (!isoCode || typeof isoCode !== 'string') return '';
  return isoCode
    .toUpperCase()
    .replace(/./g, (ch) => String.fromCodePoint(127397 + ch.charCodeAt(0)));
};
// Utilidad: diferir actualizaciones al siguiente frame para no chocar con el cierre del menú nativo del <select>
const defer = (cb) => {
  if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
    window.requestAnimationFrame(() => cb());
  } else {
    setTimeout(() => cb(), 0);
  }
};

// Eliminado CountrySelect para evitar problemas con portales en React 19.

// Dropdown de País (versión simple para estabilidad)
const CountryDropdown = ({ value, onChange, countries, disabled, hasError }) => {
  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={`w-full h-11 px-4 border ${hasError ? 'border-red-500' : 'border-gray-300'} rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none`}
    >
      <option value="">Seleccione un país</option>
      {countries.map((c) => (
        <option key={c.isoCode} value={c.isoCode}>{c.name}</option>
      ))}
    </select>
  );
};

// Separate Authentication Component to prevent re-renders
const AuthForm = ({ authMode, onSubmit, onToggleMode, onBackToHome, onForgotPassword }) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    age: '',
    cedula: '',
    gender: 'male',
    phone: '',
    address: '',
    countryCode: 'EC',
    stateCode: '',
    city: '',
    avatar: null,
    avatarPreview: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});

  const handleInputChange = useCallback((field) => (e) => {
    setFormData(prev => ({
      ...prev,
      [field]: e.target.value
    }));
  }, []);

  // Derived lists for country/state/city
  const countries = useMemo(() => Country.getAllCountries(), []);
  const states = useMemo(() => formData.countryCode ? State.getStatesOfCountry(formData.countryCode) : [], [formData.countryCode]);
  const cities = useMemo(() => (formData.countryCode && formData.stateCode) ? City.getCitiesOfState(formData.countryCode, formData.stateCode) : [], [formData.countryCode, formData.stateCode]);

  const validateClient = useCallback(() => {
    const err = {};
    const emailRegex = /.+@.+\..+/;
    if (!emailRegex.test(formData.email)) err.email = 'Correo inválido';
    if (authMode === 'register') {
      if (!formData.name.trim()) {
        err.name = 'Nombre requerido';
      } else {
        const nameParts = formData.name.trim().split(/\s+/).filter(Boolean);
        if (nameParts.length < 4) {
          err.name = 'Ingrese 2 nombres y 2 apellidos';
        }
      }
      if (!formData.age || isNaN(Number(formData.age)) || Number(formData.age) < 1 || Number(formData.age) > 120) err.age = 'Edad inválida';
      if (!/^\d{10}$/.test(formData.cedula)) err.cedula = 'Cédula debe tener 10 dígitos';
      // Validate international phone (E.164) if provided
      if (!formData.phone || !isValidPhoneNumber(formData.phone)) {
        err.phone = 'Número de teléfono inválido';
      }
      // Require country/state/city (when lists are available)
      if (!formData.countryCode) err.country = 'Selecciona un país';
      if (states.length > 0 && !formData.stateCode) err.state = 'Selecciona una provincia/estado';
      if (cities.length > 0 && !formData.city) err.city = 'Selecciona una ciudad';
  if (!formData.address || formData.address.trim().length < 1) err.address = 'Dirección requerida';
      const pw = formData.password;
      if (!pw || pw.length < 8 || !/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/\d/.test(pw) || !/[^A-Za-z0-9]/.test(pw)) {
        err.password = 'La contraseña debe tener 8+ caracteres e incluir mayúscula, minúscula, número y símbolo';
      }
      if (formData.password !== formData.confirmPassword) err.confirmPassword = 'Las contraseñas no coinciden';
          // Avatar (opcional) validaciones
          if (formData.avatar) {
            const file = formData.avatar;
            const allowed = ['image/jpeg','image/jpg','image/png','image/webp','image/gif'];
            if (file.size > 5 * 1024 * 1024) err.avatar = 'Máximo 5MB';
            if (!allowed.includes(file.type)) err.avatar = 'Solo JPG, PNG, WEBP o GIF';
          } else {
            err.avatar = 'La foto de perfil es obligatoria';
          }
    }
    setErrors(err);
    return Object.keys(err).length === 0;
  }, [formData, authMode, states.length, cities.length]);

  const handleSubmit = useCallback((e) => {
    e.preventDefault();
    if (!validateClient()) return;
    // Enrich address with city/state/country names before submitting to backend
    const countryName = formData.countryCode ? Country.getCountryByCode(formData.countryCode)?.name : '';
    const stateName = (formData.countryCode && formData.stateCode) ? State.getStateByCodeAndCountry(formData.stateCode, formData.countryCode)?.name : '';
    const enrichedAddress = [formData.address, formData.city, stateName, countryName]
      .filter(Boolean)
      .join(', ');
    onSubmit({ ...formData, address: enrichedAddress });
  }, [formData, onSubmit, validateClient]);

  const toggleMode = useCallback(() => {
    // Reset also avatar fields
    setFormData({ name: '', email: '', password: '', confirmPassword: '', age: '', cedula: '', gender: 'male', phone: '', address: '', countryCode: 'EC', stateCode: '', city: '', avatar: null, avatarPreview: '' });
    onToggleMode();
  }, [onToggleMode]);

  return (
    <div className="min-h-screen bg-[#f3f5fb] flex flex-col items-center justify-center px-4">
      {/* Branding image */}
      <div className="text-center mb-6">
        <img
          src="/Logo_inicio.png"
          alt="VisionCare Web"
          className="mx-auto h-20 md:h-24 w-auto object-contain"
          loading="eager"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
      </div>

      {/* Card */}
  <div className={`bg-white w-full rounded-2xl shadow-md p-6 sm:p-8 ${authMode === 'register' ? 'max-w-3xl sm:p-12' : 'max-w-md'}`}> 
        <h2 className="text-xl sm:text-2xl font-bold text-center text-gray-900">
          ¡Bienvenido/a a tu plataforma!
        </h2>
        <p className="text-center text-gray-500 mt-1 mb-6">
          Por favor, {authMode === 'login' ? 'inicia sesión' : 'regístrate'} con tus credenciales.
        </p>

  <form onSubmit={handleSubmit} className="">
          {authMode === 'register' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
              {/* Columna 1 */}
              <div className="flex flex-col gap-4">
                {/* Avatar uploader */}
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-16 h-16 rounded-full border overflow-hidden flex items-center justify-center bg-gray-100">
                    {formData.avatarPreview ? (
                      <img src={formData.avatarPreview} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-gray-400 text-xl" aria-hidden="true">👤</span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold">Foto de perfil <span className="text-red-600">*</span></div>
                    <div className="text-xs text-gray-500 truncate">Máximo 5MB · JPG, PNG, WEBP, GIF</div>
                    {errors.avatar && <div className="text-xs text-red-600 mt-1">{errors.avatar}</div>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <label
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-500 text-white hover:bg-orange-600 cursor-pointer whitespace-nowrap shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 transition"
                    aria-label="Actualizar foto de perfil"
                    role="button"
                    tabIndex={0}
                  >
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        const allowed = ['image/jpeg','image/jpg','image/png','image/webp','image/gif'];
                        if (file.size > 5 * 1024 * 1024) { setErrors(prev=>({ ...prev, avatar: 'Máximo 5MB' })); return; }
                        if (!allowed.includes(file.type)) { setErrors(prev=>({ ...prev, avatar: 'Solo JPG, PNG, WEBP o GIF' })); return; }
                        const url = URL.createObjectURL(file);
                        setFormData(prev => ({ ...prev, avatar: file, avatarPreview: url }));
                      }}
                    />
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M3 16.5V19.5C3 20.328 3.672 21 4.5 21H19.5C20.328 21 21 20.328 21 19.5V16.5"/>
                      <path d="M7.5 12L12 7.5L16.5 12"/>
                      <path d="M12 7.5V18"/>
                    </svg>
                    <span className="text-sm font-medium">Actualizar foto</span>
                  </label>
                  {formData.avatar && (
                    <button type="button" onClick={() => { setFormData(prev => ({ ...prev, avatar: null, avatarPreview: '' })); }} className="text-sm text-gray-600 hover:text-gray-800">Quitar</button>
                  )}
                </div>
                <div className="relative">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nombre completo</label>
                  <input
                    type="text"
                    placeholder="Ingrese sus dos nombres y dos apellidos"
                    value={formData.name}
                    onChange={handleInputChange('name')}
                    className="w-full h-11 px-4 pr-10 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    autoComplete="name"
                  />
                  <span className="absolute right-3 top-[34px] text-gray-400" aria-hidden>👤</span>
                  {errors.name && <p className="text-xs text-red-600 mt-1">{errors.name}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Edad</label>
                  <input type="number" min="1" max="120" value={formData.age} onChange={handleInputChange('age')} className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none" />
                  {errors.age && <p className="text-xs text-red-600 mt-1">{errors.age}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Género</label>
                  <select value={formData.gender} onChange={handleInputChange('gender')} className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                    <option value="male">Masculino</option>
                    <option value="female">Femenino</option>
                    <option value="other">Otro</option>
                    <option value="na">Prefiero no decir</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Cédula</label>
                  <input
                    type="text"
                    placeholder="10 dígitos"
                    inputMode="numeric"
                    value={formData.cedula}
                    maxLength={10}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                      setFormData(prev => ({ ...prev, cedula: value }));
                    }}
                    className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                  {errors.cedula && <p className="text-xs text-red-600 mt-1">{errors.cedula}</p>}
                </div>
              </div>
              {/* Columna 2 */}
              <div className="flex flex-col gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">País</label>
                  <CountryDropdown
                    value={formData.countryCode}
                    countries={countries}
                    disabled={false}
                    hasError={!!errors.country}
                    onChange={(countryCode) => {
                      defer(() => {
                        setFormData(prev => ({ ...prev, countryCode, stateCode: '', city: '' }));
                      });
                    }}
                  />
                  {errors.country && <p className="text-xs text-red-600 mt-1">{errors.country}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Provincia/Estado</label>
                  <select
                    key={`state-${formData.countryCode}`}
                    value={formData.stateCode}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (e.target && typeof e.target.blur === 'function') e.target.blur();
                      defer(() => {
                        setFormData(prev => ({ ...prev, stateCode: value, city: '' }));
                      });
                    }}
                    className={`w-full h-11 px-4 border ${(errors.state) ? 'border-red-500' : 'border-gray-300'} rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none`}
                    disabled={!formData.countryCode || states.length === 0}
                  >
                    <option value="">{states.length ? 'Seleccione una provincia/estado' : 'No hay datos'}</option>
                    {states.map(s => (
                      <option key={`${s.countryCode}-${s.isoCode}`} value={s.isoCode}>{s.name}</option>
                    ))}
                  </select>
                  {errors.state && <p className="text-xs text-red-600 mt-1">{errors.state}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
                  <select
                    key={`city-${formData.stateCode}`}
                    value={formData.city}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (e.target && typeof e.target.blur === 'function') e.target.blur();
                      defer(() => {
                        setFormData(prev => ({ ...prev, city: value }));
                      });
                    }}
                    className={`w-full h-11 px-4 border ${(errors.city) ? 'border-red-500' : 'border-gray-300'} rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none`}
                    disabled={!formData.stateCode || cities.length === 0}
                  >
                    <option value="">{cities.length ? 'Seleccione una ciudad' : 'No hay datos'}</option>
                    {cities.map(city => (
                      <option key={`${city.name}-${city.stateCode}-${city.countryCode}`} value={city.name}>{city.name}</option>
                    ))}
                  </select>
                  {errors.city && <p className="text-xs text-red-600 mt-1">{errors.city}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
                  <div className="[&_.PhoneInput]:w-full">
                    <PhoneInput
                      international
                      key={formData.countryCode}
                      defaultCountry={formData.countryCode || 'EC'}
                      flags={FLAG_ICONS}
                      placeholder="Ingresa tu número"
                      value={formData.phone}
                      onChange={(value) => setFormData(prev => ({ ...prev, phone: value || '' }))}
                      className={`PhoneInput w-full ${errors.phone ? 'phone-input-error' : ''}`}
                    />
                  </div>
                  {errors.phone && <p className="text-xs text-red-600 mt-1">{errors.phone}</p>}
                  <p className="text-xs text-gray-500 mt-1">Incluye el código del país. Ej: +593 99 999 9999</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
                  <input type="text" value={formData.address} onChange={handleInputChange('address')} className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none" />
                  {errors.address && <p className="text-xs text-red-600 mt-1">{errors.address}</p>}
                </div>
              </div>

              {/* Credenciales de cuenta (email y contraseñas) */}
              <div className="md:col-span-2">
                <div className="relative">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Correo electrónico</label>
                  <input
                    type="email"
                    placeholder="Ingrese nombre de usuario"
                    value={formData.email}
                    onChange={handleInputChange('email')}
                    className="w-full h-11 px-4 pr-10 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    required
                    autoComplete="email"
                  />
                  <span className="absolute right-3 top-[34px] text-gray-400" aria-hidden>📧</span>
                </div>
              </div>

              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Ingrese su contraseña"
                  value={formData.password}
                  onChange={handleInputChange('password')}
                  className="w-full h-11 px-4 pr-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  required
                  autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-2 top-[30px] text-gray-500 hover:text-gray-700 px-2 py-1"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? '🙈' : '👁️'}
                </button>
                {errors.password && <p className="text-xs text-red-600 mt-1">{errors.password}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar contraseña</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Repita su contraseña"
                  value={formData.confirmPassword}
                  onChange={handleInputChange('confirmPassword')}
                  className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  autoComplete="new-password"
                />
                {errors.confirmPassword && <p className="text-xs text-red-600 mt-1">{errors.confirmPassword}</p>}
              </div>

              <div className="md:col-span-2">
                <p className="text-xs text-gray-500">La contraseña debe tener al menos 8 caracteres e incluir mayúscula, minúscula, número y símbolo.</p>
              </div>
            </div>
          )}

          {/* Campos de login (email y contraseña) cuando NO es registro */}
          {authMode === 'login' && (
            <>
              <div className="relative">
                <label className="block text-sm font-medium text-gray-700 mb-1">Correo electrónico</label>
                <input
                  type="email"
                  placeholder="Ingrese nombre de usuario"
                  value={formData.email}
                  onChange={handleInputChange('email')}
                  className="w-full h-11 px-4 pr-10 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  required
                  autoComplete="email"
                />
                <span className="absolute right-3 top-[34px] text-gray-400" aria-hidden>📧</span>
              </div>

              <div className="relative mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Ingrese su contraseña"
                  value={formData.password}
                  onChange={handleInputChange('password')}
                  className="w-full h-11 px-4 pr-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  required
                  autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-2 top-[30px] text-gray-500 hover:text-gray-700 px-2 py-1"
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPassword ? '🙈' : '👁️'}
                </button>
                {errors.password && <p className="text-xs text-red-600 mt-1">{errors.password}</p>}
              </div>
            </>
          )}

          <button
            type="submit"
            className="w-full bg-[#6b75c9] hover:bg-[#5a62b3] text-white h-11 rounded-xl font-semibold transition-colors"
          >
            {authMode === 'login' ? 'Continuar' : 'Crear cuenta'}
          </button>
        </form>

        {/* Helper links */}
        {authMode === 'login' ? (
          <div className="text-center mt-4 text-sm">
            <button
              type="button"
              onClick={() => onForgotPassword && onForgotPassword()}
              className="text-indigo-600 hover:underline font-medium"
            >
              ¿Olvidaste tus datos? Recupéralos aquí.
            </button>
          </div>
        ) : null}

        <p className="text-center mt-4 text-sm">
          {authMode === 'login' ? '¿No tienes cuenta? ' : '¿Ya tienes cuenta? '}
          <button onClick={toggleMode} className="text-indigo-600 hover:underline font-semibold">
            {authMode === 'login' ? 'Regístrate aquí' : 'Inicia sesión'}
          </button>
        </p>

        <div className="flex justify-center mt-4">
          <button onClick={onBackToHome} className="text-gray-500 hover:text-gray-700 text-sm">← Volver al inicio</button>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-6 text-xs text-gray-400 text-center">
        Copyright © {new Date().getFullYear()} VisionCare Web. Todos los derechos reservados.
      </div>
    </div>
  );
};

// Stable Reset Password View as a top-level component to avoid remounting on each keystroke
const ResetPasswordView = ({ resetEmail, setResetEmail, onBackToAuth }) => {
  const emailValid = /.+@+.+\..+/.test((resetEmail || '').trim());
  const submitting = false; // placeholder until Google integration
  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-50 to-white flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <img
            src="/Logo_inicio.png"
            alt="VisionCare Web"
            className="mx-auto h-16 md:h-20 w-auto mb-4 object-contain"
            onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }}
          />
          <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">Recupera tu acceso</h1>
          <p className="text-sm text-gray-500 mt-2">Te enviaremos un enlace para restablecer tu contraseña.</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-6 md:p-8">
          <div className="mb-5">
            <label className="block text-sm font-medium text-gray-700 mb-1">Correo electrónico</label>
            <div className="relative">
              <input
                type="email"
                placeholder="tu@correo.com"
                value={resetEmail}
                onChange={(e) => setResetEmail(e.target.value)}
                className={`w-full h-11 pr-11 px-4 border ${emailValid || resetEmail === '' ? 'border-gray-300' : 'border-red-500'} rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none`}
              />
              <span className="absolute right-3 top-[10px] text-gray-400" aria-hidden>📧</span>
            </div>
            {!emailValid && resetEmail !== '' && (
              <p className="text-xs text-red-600 mt-1">Ingresa un correo válido.</p>
            )}
            <p className="text-xs text-gray-500 mt-2">Usa el correo con el que te registraste.</p>
          </div>

          <button
            type="button"
            disabled={!emailValid || submitting}
            className={`w-full h-11 rounded-xl font-semibold text-white transition-colors ${(!emailValid || submitting) ? 'bg-indigo-300 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700'}`}
            onClick={() => { try { alert('Enlace de restablecimiento enviado si el correo existe (pendiente Google).'); } catch {} }}
          >
            {submitting ? 'Enviando…' : 'Enviar enlace'}
          </button>

          <div className="flex items-center my-6">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="px-3 text-xs text-gray-400">o</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <button
            type="button"
            className="w-full h-11 rounded-xl font-semibold border border-gray-300 bg-white hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
            onClick={() => { try { alert('Continuar con Google (pendiente integración).'); } catch {} }}
          >
            <span>🔐</span>
            <span>Continuar con Google</span>
          </button>

          <div className="text-center mt-6">
            <button className="text-gray-600 hover:underline text-sm" onClick={onBackToAuth}>
              ← Volver a Iniciar sesión
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Enhanced Webcam Component for Eye Capture
const WebcamCapture = ({ onCapture, onClose }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, []);

  // Ensure camera stops when tab/window becomes hidden
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState !== 'visible') {
        stopCamera();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    const handleBeforeUnload = () => {
      try { stopCamera(); } catch {}
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('beforeunload', handleBeforeUnload);
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
        streamRef.current = stream;
        
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
    try {
      const stream = streamRef.current || (videoRef.current ? videoRef.current.srcObject : null);
      if (stream) {
        try {
          const tracks = stream.getTracks ? stream.getTracks() : [];
          tracks.forEach(track => {
            try { track.stop(); } catch {}
          });
        } catch {}
      }
      if (videoRef.current) {
        try { videoRef.current.pause(); } catch {}
        try { videoRef.current.srcObject = null; } catch {}
        try { videoRef.current.removeAttribute('src'); } catch {}
        try { videoRef.current.src = ''; } catch {}
        try { videoRef.current.load(); } catch {}
      }
    } catch {}
    streamRef.current = null;
    setIsStreaming(false);
  };

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;

    setIsCapturing(true);
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    // Pause the stream right away to hint the browser to release camera ASAP
    try { video.pause(); } catch {}

    // Set canvas size to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw video frame to canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Immediately stop the camera so the LED turns off right after clicking
    stopCamera();

    // Convert to blob
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], 'eye-capture.jpg', { type: 'image/jpeg' });
        onCapture(file);
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

// Lightweight loading screen with spinner and skeletons
const LoadingScreen = () => (
  <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    {/* Top skeleton bar (like navbar) */}
    <div className="bg-white shadow-sm">
      <div className="container mx-auto p-4">
        <div className="animate-pulse flex items-center gap-3">
          <div className="h-8 w-8 bg-gray-200 rounded-full"></div>
          <div className="h-4 w-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    </div>

    {/* Center spinner */}
    <div className="flex items-center justify-center px-4" style={{ minHeight: 'calc(100vh - 64px)' }}>
      <div className="text-center">
        <div className="mx-auto mb-4 h-12 w-12 border-4 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" aria-label="Cargando"></div>
        <p className="text-gray-600 font-medium">Cargando tu sesión…</p>
        <p className="text-gray-400 text-sm mt-1">Verificando credenciales y preparando tu panel</p>
      </div>
    </div>
  </div>
);

const VisionCareApp = () => {
  // Router hooks
  const location = useLocation();
  const navigate = useNavigate();

  const [user, setUser] = useState(null);
  const [currentView, setCurrentView] = useState(() => {
    try {
      // Prefer URL path on first load
      const p = (typeof window !== 'undefined' && window.location && window.location.pathname) ? window.location.pathname : '/';
      const initialFromPath = (
        !p || p === '/' ? 'home' :
        p.startsWith('/auth') ? 'auth' :
        p.startsWith('/start') ? 'start' :
        p.startsWith('/dashboard') ? 'dashboard' :
        p.startsWith('/analyze') ? 'analyze' :
        p.startsWith('/results') ? 'results' :
        p.startsWith('/history') ? 'history' :
        p.startsWith('/profile') ? 'profile' :
        p.startsWith('/change-password') ? 'change-password' : 'home'
      );
      return initialFromPath;
    } catch {
      return 'home';
    }
  });
  const [authMode, setAuthMode] = useState(() => {
    try {
      const saved = localStorage.getItem('authMode');
      return saved === 'register' || saved === 'login' ? saved : 'login';
    } catch {
      return 'login';
    }
  });
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisExtras, setAnalysisExtras] = useState(null); // { uncertainty, quality, runtime }

  const getUncertaintyLabel = useCallback((unc) => {
    if (!unc || typeof unc.entropy !== 'number') return null;
    const norm = (typeof unc.entropy_normalized === 'number')
      ? Math.min(1, Math.max(0, Number(unc.entropy_normalized)))
      : (() => {
          const ent = Number(unc.entropy || 0);
          const cls = analysisExtras?.runtime?.class_names?.length || 3;
          const maxEnt = Math.log(cls || 3) || 1;
          return Math.min(1, Math.max(0, ent / (maxEnt || 1)));
        })();
    // thresholds: <0.35 low, <0.7 medium, else high
    if (norm < 0.35) return { label: 'Baja', color: 'text-green-700', bg: 'bg-green-100' };
    if (norm < 0.7) return { label: 'Media', color: 'text-amber-700', bg: 'bg-amber-100' };
    return { label: 'Alta', color: 'text-red-700', bg: 'bg-red-100' };
  }, [analysisExtras]);
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  // Track where the current preview/file comes from: 'upload' | 'webcam'
  const [previewSource, setPreviewSource] = useState(null);
  // Preserve last uploaded file/preview to restore when going back to "Subir Imagen"
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState(null);
  const [showWebcam, setShowWebcam] = useState(false);
  const [captureMode, setCaptureMode] = useState('upload'); // 'upload' or 'webcam'
  const [resetEmail, setResetEmail] = useState('');

  // Mapping between internal views and URL paths
  const viewToPath = useCallback((view) => {
    switch (view) {
      case 'home': return '/';
      case 'auth': return '/auth';
      case 'start': return '/start';
      case 'dashboard': return '/dashboard';
      case 'analyze': return '/analyze';
      case 'results': return '/results';
      case 'reset-password': return '/reset-password';
      case 'history': return '/history';
      case 'profile': return '/profile';
      case 'change-password': return '/change-password';
      default: return '/';
    }
  }, []);
  const pathToView = useCallback((pathname) => {
    if (!pathname || pathname === '/') return 'home';
    if (pathname.startsWith('/auth')) return 'auth';
    if (pathname.startsWith('/start')) return 'start';
    if (pathname.startsWith('/dashboard')) return 'dashboard';
    if (pathname.startsWith('/analyze')) return 'analyze';
    if (pathname.startsWith('/results')) return 'results';
    if (pathname.startsWith('/reset-password')) return 'reset-password';
    if (pathname.startsWith('/history')) return 'history';
    if (pathname.startsWith('/profile')) return 'profile';
    if (pathname.startsWith('/change-password')) return 'change-password';
    return 'home';
  }, []);

  // Restaurar vista/mode persistidos antes de chequear auth
  useEffect(() => {
    try {
      const savedMode = localStorage.getItem('authMode');
      if (savedMode === 'login' || savedMode === 'register') {
        setAuthMode(savedMode);
      }
      const savedView = localStorage.getItem('currentView');
      // Solo restaurar 'auth' si no hay usuario aún; dashboard se forzará tras validar token
      if (savedView === 'auth') {
        setCurrentView('auth');
      }
    } catch {
      // Ignorar errores de acceso a localStorage (p. ej., privacy mode)
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // Wait for profile to determine view; avoid flashing Home
      fetchUserInfo().finally(() => setIsAuthLoading(false));
    } else {
      setIsAuthLoading(false);
    }
  }, []);

  // Initialize currentView from URL on first render and when the pathname changes externally
  useEffect(() => {
    const nextView = pathToView(location.pathname || '/');
    setCurrentView((prev) => prev === nextView ? prev : nextView);
  }, [location.pathname]);

  // Persistir vista y modo para mantener estado tras refresh
  useEffect(() => {
    try { localStorage.setItem('currentView', currentView); } catch {}
  }, [currentView]);

  // Keep URL updated when currentView changes from UI actions
  useEffect(() => {
    const target = viewToPath(currentView);
    if (location.pathname !== target) {
      navigate(target, { replace: false });
    }
  }, [currentView]);

  // Auto-cargar historial cuando el usuario entra en la vista correspondiente
  useEffect(() => {
    if (currentView === 'history' && user) {
      loadAnalysisHistory();
    }
  }, [currentView, user]);
  useEffect(() => {
    try { localStorage.setItem('authMode', authMode); } catch {}
  }, [authMode]);

  // ResetPasswordPage removed; using stable component ResetPasswordView defined above.

  // Alternar modo de auth y persistir inmediatamente
  const toggleAuthMode = useCallback(() => {
    setAuthMode(prev => {
      const next = prev === 'login' ? 'register' : 'login';
      try { localStorage.setItem('authMode', next); } catch {}
      return next;
    });
  }, []);

  const fetchUserInfo = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/auth/profile/`);
      setUser(response.data);
      // Ensure the app stays inside the system after refresh
      setCurrentView('start');
    } catch (error) {
      console.error('Error fetching user info:', error);
      localStorage.removeItem('token');
      delete axios.defaults.headers.common['Authorization'];
    }
  }, []);

  const { toast } = useToast();
  const handleAuth = useCallback(async (formData) => {
    // Mostrar la misma pantalla de carga global mientras se procesa login/registro
    setIsAuthLoading(true);
    try {
      if (authMode === 'register') {
        // Django expects separate first_name and last_name
        // Split full name to support 2 nombres y 2 apellidos
        const parts = (formData.name || '').trim().split(/\s+/).filter(Boolean);
        let firstName = '';
        let lastName = '';
        if (parts.length >= 4) {
          firstName = `${parts[0]} ${parts[1]}`.trim();
          lastName = `${parts[parts.length - 2]} ${parts[parts.length - 1]}`.trim();
        } else if (parts.length === 3) {
          // Assume: 2 nombres + 1 apellido
          firstName = `${parts[0]} ${parts[1]}`.trim();
          lastName = parts[2];
        } else if (parts.length === 2) {
          firstName = parts[0];
          lastName = parts[1];
        } else if (parts.length === 1) {
          firstName = parts[0];
          lastName = parts[0];
        } else {
          firstName = '';
          lastName = '';
        }
        
        const registerData = {
          email: formData.email,
          username: formData.email, // Use email as username
          first_name: firstName,
          last_name: lastName,
          password: formData.password,
          password_confirm: formData.confirmPassword || formData.password,
          age: Number(formData.age),
          cedula: formData.cedula,
          gender: formData.gender,
          phone: formData.phone,
          address: formData.address,
          country: Country.getCountryByCode(formData.countryCode)?.name || '',
          state: (formData.stateCode && formData.countryCode) ? State.getStateByCodeAndCountry(formData.stateCode, formData.countryCode)?.name || '' : '',
          city: formData.city || ''
        };
        
  const response = await axios.post(`${API}/auth/register/`, registerData);
        
        // Django returns tokens immediately on registration
        if (response.data.tokens) {
          const token = response.data.tokens.access;
          localStorage.setItem('token', token);
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          let newUser = response.data.user;
          // If avatar chosen, upload it now
          if (formData.avatar) {
            try {
              const fd = new FormData();
              fd.append('avatar', formData.avatar);
              const up = await axios.post(`${API}/auth/avatar/`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
              newUser = { ...newUser, avatar_url: up.data?.avatar_url || newUser.avatar_url };
            } catch (e) {
              console.error('Avatar upload after register failed', e?.response || e);
              toast({ title: 'Avatar no subido', description: 'Puedes actualizar tu foto desde el perfil.', variant: 'default' });
            }
          }
          setUser(newUser);
          setCurrentView('start');
        } else {
          toast({ title: 'Registro exitoso', description: 'Inicia sesión para continuar.' });
          setAuthMode('login');
        }
      } else {
        const response = await axios.post(`${API}/auth/login/`, {
          email: formData.email,
          password: formData.password
        });
        
        const token = response.data.tokens.access;
        localStorage.setItem('token', token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  setUser(response.data.user);
  setCurrentView('start');
      }
    } catch (error) {
      // Extrae el primer mensaje útil del backend en vez de mostrar uno genérico
  let errorMessage = 'No se pudo autenticar';
      const data = error?.response?.data;
      if (data) {
        if (typeof data === 'string') {
          errorMessage = data;
        } else if (data.detail || data.message) {
          errorMessage = data.detail || data.message;
        } else if (Array.isArray(data) && data.length) {
          errorMessage = (data[0]?.msg || data[0]?.message || data[0]) + '';
        } else if (typeof data === 'object') {
          // Busca el primer campo con errores y muestra su mensaje
          const firstKey = Object.keys(data)[0];
          const val = data[firstKey];
          if (Array.isArray(val)) {
            errorMessage = val[0] + '';
          } else if (typeof val === 'string') {
            errorMessage = val;
          }
        }
      }
      console.error('Auth error:', error?.response || error);
      toast({ title: 'Error de autenticación', description: errorMessage, variant: 'destructive' });
    } finally {
      // Ocultar pantalla de carga al terminar (éxito o error)
      setIsAuthLoading(false);
    }
  }, [authMode]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
    setCurrentView('home');
    try { window.history.pushState({}, '', '/'); } catch {}
    setAnalysisResult(null);
    setAnalysisHistory([]);
    try {
      localStorage.removeItem('lastAnalysisResult');
      localStorage.removeItem('lastAnalysisExtras');
      localStorage.removeItem('currentView');
    } catch {}
  }, []);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files[0];
    if (file) {
      processSelectedFile(file, 'upload');
    }
  }, []);

  const processSelectedFile = useCallback((file, source = 'upload') => {
    // Alinear validaciones con el backend (DRF): JPEG/JPG/PNG/WEBP hasta 10MB
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      toast({ title: 'Archivo demasiado grande', description: 'El archivo debe pesar menos de 10MB.', variant: 'destructive' });
      return;
    }
    const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      toast({ title: 'Tipo de archivo inválido', description: 'Solo se permiten imágenes JPEG, PNG o WEBP.', variant: 'destructive' });
      return;
    }
    
    setSelectedFile(file);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    if (source === 'upload') {
      setPreviewSource('upload');
      // Revoke previous upload blob if any
      if (uploadPreviewUrl && uploadPreviewUrl.startsWith('blob:')) {
        try { URL.revokeObjectURL(uploadPreviewUrl); } catch {}
      }
      setUploadPreviewUrl(url);
      setUploadFile(file);
    } else if (source === 'webcam') {
      setPreviewSource('webcam');
    }
  }, [uploadPreviewUrl, toast]);

  const handleWebcamCapture = useCallback((file) => {
    processSelectedFile(file, 'webcam');
    setShowWebcam(false);
    setCaptureMode('webcam');
  }, [processSelectedFile]);

  // When switching back to 'upload', restore last uploaded preview automatically
  useEffect(() => {
    if (captureMode === 'upload') {
      if (uploadFile && previewSource !== 'upload') {
        setSelectedFile(uploadFile);
        setPreviewUrl(uploadPreviewUrl);
        setPreviewSource('upload');
      }
    }
  }, [captureMode, uploadFile, uploadPreviewUrl, previewSource]);

  const analyzeImage = useCallback(async () => {
    if (!selectedFile) {
  toast({ title: 'Falta la imagen', description: 'Selecciona o captura una imagen para analizar.', variant: 'destructive' });
      return;
    }

    setIsAnalyzing(true);
    const formData = new FormData();
    formData.append('image', selectedFile); // Django expects 'image' field

    try {
      // Importante: NO establecer manualmente 'Content-Type' cuando se envía FormData.
      // El navegador añade el boundary correcto; si lo forzamos, Django no podrá parsear el archivo.
      // Adjuntamos Authorization explícitamente por robustez ante reinicios de axios defaults.
      const token = localStorage.getItem('token');
      const response = await axios.post(`${API}/analyze-image/`, formData, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      // Save main analysis object
      setAnalysisResult(response.data.analysis); // Django returns nested analysis object
      // Save extras (uncertainty, quality, runtime). Fallback to ai_raw_response if needed
      const extras = {
        uncertainty: response.data.uncertainty || response.data.analysis?.ai_raw_response?.uncertainty || null,
        quality: response.data.quality || response.data.analysis?.ai_raw_response?.quality || null,
        runtime: response.data.runtime || response.data.analysis?.ai_raw_response?.runtime || null,
        processed_image_url: response.data.processed_image_url || response.data.analysis?.ai_raw_response?.processed_image_url || null,
      };
      setAnalysisExtras(extras);
      setCurrentView('results');
      try {
        localStorage.setItem('lastAnalysisResult', JSON.stringify(response.data.analysis));
        localStorage.setItem('lastAnalysisExtras', JSON.stringify(extras));
        localStorage.setItem('currentView', 'results');
      } catch {}
      // Cleanup: do not keep blob URLs or file after analysis succeeds
      try {
        if (previewUrl && typeof previewUrl === 'string' && previewUrl.startsWith('blob:')) {
          URL.revokeObjectURL(previewUrl);
        }
        if (uploadPreviewUrl && typeof uploadPreviewUrl === 'string' && uploadPreviewUrl.startsWith('blob:')) {
          URL.revokeObjectURL(uploadPreviewUrl);
        }
      } catch {}
      setPreviewUrl(null);
      setUploadPreviewUrl(null);
      setSelectedFile(null);
      setUploadFile(null);
      setPreviewSource(null);
      loadAnalysisHistory();
    } catch (error) {
      // Intentar mostrar errores del serializer (p.ej., { image: ["Only JPEG..."] })
      const status = error?.response?.status;
      const data = error?.response?.data;
      let errorMessage = data?.error || data?.detail || 'No se pudo analizar la imagen';
      if (data && data.image) {
        const imgErr = Array.isArray(data.image) ? data.image[0] : data.image;
        errorMessage = typeof imgErr === 'string' ? imgErr : errorMessage;
      }
      if (status === 401) {
        errorMessage = 'Sesión expirada o no autorizada. Inicia sesión nuevamente.';
      }
      // Como último recurso mostrar el mensaje de red
      if (!data && error?.message) {
        errorMessage = `${errorMessage} (${error.message})`;
      }
      console.error('Analyze error:', { status, data, error });
      toast({ title: 'Análisis fallido', description: errorMessage, variant: 'destructive' });
    } finally {
      setIsAnalyzing(false);
    }
  }, [selectedFile]);

  const loadAnalysisHistory = useCallback(async () => {
    try {
      setHistoryLoading(true);
      const response = await axios.get(`${API}/history/`);
      const data = response.data;
      const items = Array.isArray(data) ? data : (data && Array.isArray(data.results) ? data.results : []);
      setAnalysisHistory(items);
    } catch (error) {
      const status = error?.response?.status;
      if (status === 401) {
        // Token inválido: limpiar sesión mínima pero no forzar logout inmediato
        console.warn('Historia: 401 no autorizado. Requiere reautenticación.');
      } else {
        console.error('Error loading history:', error?.response || error);
      }
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const clearHistory = useCallback(async () => {
    const confirmed = window.confirm('¿Seguro que deseas borrar TODO tu historial de análisis? Esta acción no se puede deshacer.');
    if (!confirmed) return;
    try {
      setHistoryLoading(true);
      await axios.delete(`${API}/history/clear/`);
      setAnalysisHistory([]);
      try { toast({ title: 'Historial borrado', description: 'Se eliminaron tus análisis previos.' }); } catch {}
    } catch (error) {
      console.error('Error clearing history:', error?.response || error);
      try { toast({ title: 'No se pudo borrar', description: error?.response?.data?.detail || 'Intenta de nuevo', variant: 'destructive' }); } catch {}
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const downloadAnalysisPDF = useCallback(async (analysisId) => {
    try {
      const response = await axios.get(`${API}/download-analysis/${analysisId}/`, {
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
  toast({ title: 'Descarga fallida', description: error.response?.data?.detail || error.message, variant: 'destructive' });
    }
  }, []);

  // --- Persistencia de resultado y extras (si cambian manualmente) ---
  useEffect(() => {
    try {
      if (analysisResult) {
        localStorage.setItem('lastAnalysisResult', JSON.stringify(analysisResult));
        localStorage.setItem('currentView', 'results');
      }
    } catch {}
  }, [analysisResult]);

  useEffect(() => {
    try {
      if (analysisExtras) {
        localStorage.setItem('lastAnalysisExtras', JSON.stringify(analysisExtras));
      }
    } catch {}
  }, [analysisExtras]);

  // Rehidratación tras refrescar
  useEffect(() => {
    try {
      const savedView = localStorage.getItem('currentView');
      if (savedView === 'results') {
        const savedResult = localStorage.getItem('lastAnalysisResult');
        const savedExtras = localStorage.getItem('lastAnalysisExtras');
        if (savedResult) {
          try { setAnalysisResult(JSON.parse(savedResult)); } catch {}
        }
        if (savedExtras) {
          try { setAnalysisExtras(JSON.parse(savedExtras)); } catch {}
        }
        setCurrentView('results');
      }
    } catch {}
  }, []);

  // Nuevo diagnóstico: limpiar estado y volver al panel interno (dashboard)
  const handleNewDiagnosis = useCallback(() => {
    setAnalysisResult(null);
    setAnalysisExtras(null);
    setSelectedFile(null);
    setPreviewUrl(null);
    try {
      localStorage.removeItem('lastAnalysisResult');
      localStorage.removeItem('lastAnalysisExtras');
      localStorage.setItem('currentView', 'dashboard');
    } catch {}
    setCurrentView('dashboard');
  }, []);

  const getDiagnosisColor = useCallback((diagnosis) => {
    const key = ((diagnosis ?? '') + '').toLowerCase();
    switch (key) {
      case 'normal': return 'text-green-600';
      case 'cataracts': return 'text-orange-600';
      case 'conjunctivitis': return 'text-red-600';
      case 'multiple conditions': return 'text-purple-600';
      default: return 'text-gray-600';
    }
  }, []);

  const getDiagnosisIcon = useCallback((diagnosis) => {
    const key = ((diagnosis ?? '') + '').toLowerCase();
    switch (key) {
      case 'normal': return '✅';
      case 'cataracts': return '🔍';
      case 'conjunctivitis': return '🔴';
      case 'multiple conditions': return '⚠️';
      default: return '❓';
    }
  }, []);

  // Helpers for diagnosis display
const DIAGNOSIS_ES = {
  normal: 'Normal',
  conjunctivitis: 'Conjuntivitis',
  cataracts: 'Cataratas',
  'multiple conditions': 'Múltiples condiciones',
  opacidades_menores: 'Opacidades menores',
  redness_minor: 'Rojez moderada',
  unknown: 'Desconocido'
};

const SEVERITY_ES = {
  normal: 'Normal',
  mild: 'Leve',
  moderate: 'Moderada',
  severe: 'Severa',
};

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
            Sistema de detección de enfermedades oculares asistido por IA
          </p>
          <p className="text-lg text-gray-500 max-w-2xl mx-auto">
            Detección avanzada de cataratas y conjuntivitis usando inteligencia artificial y visión por computador. Obtén un análisis inmediato de tu salud ocular.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 mb-12">
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">🔍</div>
            <h3 className="text-xl font-semibold mb-2">Análisis IA Avanzado</h3>
            <p className="text-gray-600">
              Nuestra IA usa OpenCV y modelos de aprendizaje automático para detectar cataratas y conjuntivitis con alta precisión.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">📱</div>
            <h3 className="text-xl font-semibold mb-2">Subida de Imagen Fácil</h3>
            <p className="text-gray-600">
              Sube una foto clara de tu ojo y obtén resultados de análisis instantáneos con recomendaciones detalladas.
            </p>
          </div>
          <div className="bg-white p-6 rounded-lg shadow-lg">
            <div className="text-3xl mb-4">📊</div>
            <h3 className="text-xl font-semibold mb-2">Seguimiento</h3>
            <p className="text-gray-600">
              Haz seguimiento de tu salud ocular a lo largo del tiempo con historial detallado y comparaciones.
            </p>
          </div>
        </div>

        <div className="text-center">
          <button
            onClick={() => setCurrentView('auth')}
            className="bg-indigo-600 text-white px-8 py-3 rounded-lg text-lg font-semibold hover:bg-indigo-700 transition-colors"
          >
            Comenzar
          </button>
        </div>
      </div>
    </div>
  ), []);

  // Dashboard Page
  // Start Page (post-login landing) — vacío con solo la barra superior
  const StartPage = useMemo(() => () => {
    const [newsletterEmail, setNewsletterEmail] = useState('');
    const onSubscribe = useCallback((e) => {
      e?.preventDefault?.();
      const email = (newsletterEmail || '').trim();
      const ok = /.+@.+\..+/.test(email);
      if (!ok) {
        try { toast({ title: 'Correo inválido', description: 'Revisa el formato del email.', variant: 'destructive' }); } catch {}
        return;
      }
      try { toast({ title: 'Suscripción enviada', description: 'Gracias por suscribirte.' }); } catch {}
      setNewsletterEmail('');
    }, [newsletterEmail]);

    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <TopNav
          user={user}
          onGoDashboard={() => setCurrentView('start')}
          onGoProfile={() => setCurrentView('profile')}
          onGoChangePassword={() => setCurrentView('change-password')}
          onGoHistory={() => { setCurrentView('history'); }}
          onLogout={() => handleLogout()}
        />
        {/* Hero banner */}
        <div className="container mx-auto px-4 pt-6">
          <div className="rounded-3xl bg-gradient-to-r from-indigo-600 via-violet-500 to-sky-500 text-white p-6 sm:p-10">
            <div className="grid md:grid-cols-2 gap-6 items-center">
              <div>
                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold leading-tight mb-4">
                  <span className="block">Cuidamos tu visión</span>
                  <span className="block">con Inteligencia</span>
                  <span className="block">Artificial</span>
                </h1>
                <p className="text-white/90 max-w-xl mb-5">
                  Análisis ocular avanzado con IA para la detección temprana de cataratas y conjuntivitis. Basado en OpenCV y modelos de Deep Learning.
                </p>
                <button
                  type="button"
                  onClick={() => setCurrentView('dashboard')}
                  className="inline-flex items-center gap-2 bg-white text-gray-900 px-4 py-2 rounded-lg font-semibold shadow-sm hover:bg-white/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-white"
                >
                  Comenzar análisis
                </button>
              </div>
              <div className="flex justify-center md:justify-end">
                <img
                  src="/hero-visioncare.png"
                  alt="VisionCare Web"
                  className="w-[320px] sm:w-[440px] lg:w-[560px] h-auto object-contain drop-shadow-md"
                  onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }}
                />
              </div>
            </div>
          </div>
        </div>
        {/* Quick stats mejoradas */}
        {(() => {
          const total = analysisHistory?.length || 0;
          const avgConfidencePct = total > 0
            ? Math.round(
                (analysisHistory.reduce((s, a) => s + Number(a.confidence_score || 0), 0) / total) * 100
              )
            : 0;
          const lastDiag = total > 0 ? (analysisHistory[0]?.diagnosis || null) : null;
          const diagClass = getDiagnosisColor ? getDiagnosisColor(lastDiag) : 'text-gray-600';
          return (
            <div className="container mx-auto px-4 pt-6 w-full">
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Card: Total análisis */}
                <div className="group relative rounded-2xl bg-white shadow-lg ring-1 ring-black/5 p-5 transition hover:shadow-xl">
                  <div className="flex items-center gap-4">
                    <div className="shrink-0 rounded-xl bg-indigo-50 p-2.5 shadow-inner text-indigo-600">
                      {/* Branded eye with concentric iris and spark */}
                      <svg className="w-8 h-8" viewBox="0 0 24 24" aria-hidden="true">
                        <defs>
                          <linearGradient id="vcEyeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stopColor="#6366F1"/>
                            <stop offset="100%" stopColor="#4F46E5"/>
                          </linearGradient>
                        </defs>
                        <path d="M12 4.8C6.2 4.8 2 9.4 0.9 11.5 2 13.6 6.2 18.2 12 18.2s10-4.6 11.1-6.7C22 9.4 17.8 4.8 12 4.8z" fill="url(#vcEyeGrad)" opacity="0.22"/>
                        <circle cx="12" cy="11.5" r="3.8" fill="url(#vcEyeGrad)" opacity="0.28"/>
                        <circle cx="12" cy="11.5" r="2.2" fill="url(#vcEyeGrad)"/>
                        <circle cx="13.1" cy="10.4" r="0.7" fill="#fff"/>
                        <path d="M7.2 9.2c1-.8 2.8-1.7 4.8-1.7 2 0 3.8.9 4.8 1.7" stroke="url(#vcEyeGrad)" strokeWidth="1.2" strokeLinecap="round" fill="none" opacity="0.8"/>
                      </svg>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Análisis realizados</div>
                      <div className="text-2xl font-bold tracking-tight">{total}</div>
                    </div>
                  </div>
                  <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-transparent group-hover:ring-indigo-200/80"></div>
                </div>

                {/* Card: Confianza promedio */}
                <div className="group relative rounded-2xl bg-white shadow-lg ring-1 ring-black/5 p-5 transition hover:shadow-xl">
                  <div className="flex items-center gap-4">
                    <div className="shrink-0 rounded-xl bg-violet-50 p-2.5 shadow-inner text-violet-600">
                      {/* Dynamic gauge reflecting confidence */}
                      <svg className="w-8 h-8" viewBox="0 0 24 24" aria-hidden="true">
                        <defs>
                          <linearGradient id="vcGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#A78BFA"/>
                            <stop offset="100%" stopColor="#7C3AED"/>
                          </linearGradient>
                        </defs>
                        {/* track */}
                        <path d="M3.5 12a8.5 8.5 0 0 1 17 0" fill="none" stroke="url(#vcGaugeGrad)" strokeWidth="2" opacity="0.3" strokeLinecap="round"/>
                        {/* ticks */}
                        <path d="M12 3.5v1.3M18.01 6L17.09 6.91M20.5 12h-1.3M18.01 18.01L17.09 17.09M12 20.5v-1.3" stroke="#7C3AED" strokeWidth="1.4" strokeLinecap="round" opacity="0.6"/>
                        {/* needle */}
                        <g transform={`rotate(${(-90 + (Math.max(0, Math.min(100, Number(avgConfidencePct) || 0)) * 180) / 100).toFixed(1)} 12 12)`}>
                          <path d="M12 12L19 12" stroke="#7C3AED" strokeWidth="2.2" strokeLinecap="round"/>
                        </g>
                        <circle cx="12" cy="12" r="1.4" fill="#7C3AED"/>
                      </svg>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Confianza promedio</div>
                      <div className="text-2xl font-bold tracking-tight">{avgConfidencePct}%</div>
                    </div>
                  </div>
                  <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-transparent group-hover:ring-violet-200/80"></div>
                </div>

                {/* Card: Último diagnóstico */}
                <div className="group relative rounded-2xl bg-white shadow-lg ring-1 ring-black/5 p-5 transition hover:shadow-xl">
                  <div className="flex items-center gap-4">
                    <div className={`shrink-0 rounded-xl bg-amber-50 p-2.5 shadow-inner ${diagClass}`}>
                      {/* Diagnosis pill tag, adapts to diagnosis color via currentColor */}
                      <svg className="w-8 h-8" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M6 8a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3.5a3.5 3.5 0 0 1-1.02 2.48l-4.5 4.5a3.5 3.5 0 0 1-4.95 0L5.54 17a3.5 3.5 0 0 1-1.02-2.48V8z" fill="currentColor" opacity="0.2"/>
                        <rect x="7" y="6" width="10" height="8" rx="4" stroke="currentColor" strokeWidth="1.6" fill="none"/>
                        <circle cx="9.2" cy="8.8" r="0.9" fill="currentColor"/>
                        <path d="M12 9.8v2.4M13.2 11h-2.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                      </svg>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Último diagnóstico</div>
                      <div className={`text-lg font-semibold ${diagClass}`}>
                        {lastDiag ? (DIAGNOSIS_ES[lastDiag?.toLowerCase?.()] || lastDiag) : '—'}
                      </div>
                    </div>
                  </div>
                  <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-transparent group-hover:ring-amber-200/80"></div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Sección inspiracional con imágenes circulares */}
        <div className="container mx-auto px-4 py-10 flex-1 w-full">
          <div className="bg-white rounded-3xl border border-gray-100 p-6 md:p-10 overflow-hidden">
            <div className="grid md:grid-cols-2 gap-8 items-center">
              <div>
                <p className="text-sm font-semibold text-rose-700 tracking-widest mb-2">EN VISIONCARE</p>
                <h3 className="text-3xl md:text-5xl font-extrabold text-slate-900 leading-tight mb-4">
                  Valoramos cada <span className="text-indigo-600">etapa</span> de tu vida
                </h3>
                <p className="text-slate-600 text-base md:text-lg mb-2">
                  Nuestro propósito: brindar atención segura y de excelencia, centrada en el cuidado ocular y el bienestar de las personas.
                </p>
              </div>
              <div className="relative h-[260px] md:h-[360px]">
                <div className="absolute -right-4 top-0 w-40 h-40 md:w-56 md:h-56 rounded-full overflow-hidden ring-8 ring-white shadow-lg">
                  <img src="/start-c1.jpg" width="224" height="224" alt="Atención" className="w-full h-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
                </div>
                <div className="absolute left-0 top-10 w-48 h-48 md:w-64 md:h-64 rounded-full overflow-hidden ring-8 ring-white shadow-lg">
                  <img src="/start-c2.jpg" width="256" height="256" alt="Paciente" className="w-full h-full object-cover bg-gray-50" onError={(e)=>{e.currentTarget.style.display='none';}} />
                </div>
                <div className="absolute left-10 bottom-0 w-28 h-28 md:w-36 md:h-36 rounded-full overflow-hidden ring-8 ring-white shadow-lg">
                  <img src="/start-c3.jpg" width="144" height="144" alt="Cuidado" className="w-full h-full object-cover bg-gray-100" onError={(e)=>{e.currentTarget.style.display='none';}} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer agregado al Start */}
        <footer className="bg-[#111c2b] text-gray-300">
          <div className="container mx-auto px-4 py-10">
            {/* Newsletter + Social */}
            <div className="grid lg:grid-cols-2 gap-6 items-center mb-10">
              <div>
                <p className="text-sm text-gray-400 mb-2">¡Recibe las mejores ofertas y consejos para tu visión!</p>
                <form onSubmit={onSubscribe} className="flex max-w-3xl">
                  <input
                    type="email"
                    value={newsletterEmail}
                    onChange={(e) => setNewsletterEmail(e.target.value)}
                    placeholder="Correo electrónico"
                    className="flex-1 h-12 rounded-l-[12px] px-4 bg-white text-gray-800 focus:outline-none"
                  />
                  <button type="submit" className="h-12 px-6 rounded-r-[12px] bg-indigo-600 hover:bg-indigo-700 font-semibold">
                    SUSCRIBIRME
                  </button>
                </form>
              </div>
              <div className="lg:justify-self-end">
                <div className="text-sm text-gray-400 mb-2">Síguenos en:</div>
                <div className="flex items-center gap-3">
                  {/* Facebook badge */}
                  <a href="#" aria-label="Facebook" onClick={(e)=>e.preventDefault()} className="inline-flex items-center justify-center w-9 h-9 rounded-full shadow-sm transition hover:shadow-md hover:scale-105" title="Facebook">
                    <svg viewBox="0 0 24 24" className="w-9 h-9" aria-hidden="true">
                      <circle cx="12" cy="12" r="12" fill="#1877F2"/>
                      <path fill="#FFFFFF" d="M15 8h-1.6c-.37 0-.4.15-.4.42V10h2l-.26 2h-1.74v5h-2.1v-5H9V10h1.9V8.7C10.9 7.1 11.83 6 13.7 6H15v2z"/>
                    </svg>
                  </a>
                  {/* Instagram badge with gradient */}
                  <a href="#" aria-label="Instagram" onClick={(e)=>e.preventDefault()} className="inline-flex items-center justify-center w-9 h-9 rounded-full shadow-sm transition hover:shadow-md hover:scale-105" title="Instagram">
                    <svg viewBox="0 0 24 24" className="w-9 h-9" aria-hidden="true">
                      <defs>
                        <linearGradient id="igGrad" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0%" stop-color="#f58529"/>
                          <stop offset="40%" stop-color="#dd2a7b"/>
                          <stop offset="70%" stop-color="#8134af"/>
                          <stop offset="100%" stop-color="#515bd4"/>
                        </linearGradient>
                      </defs>
                      <circle cx="12" cy="12" r="12" fill="url(#igGrad)"/>
                      <rect x="6.5" y="6.5" width="11" height="11" rx="3.2" fill="none" stroke="#fff" strokeWidth="1.8"/>
                      <circle cx="12" cy="12" r="3.3" fill="none" stroke="#fff" strokeWidth="1.8"/>
                      <circle cx="16.4" cy="7.6" r="1.1" fill="#fff"/>
                    </svg>
                  </a>
                  {/* LinkedIn badge */}
                  <a href="#" aria-label="LinkedIn" onClick={(e)=>e.preventDefault()} className="inline-flex items-center justify-center w-9 h-9 rounded-full shadow-sm transition hover:shadow-md hover:scale-105" title="LinkedIn">
                    <svg viewBox="0 0 24 24" className="w-9 h-9" aria-hidden="true">
                      <circle cx="12" cy="12" r="12" fill="#0A66C2"/>
                      <rect x="6.7" y="9.8" width="2.4" height="7.2" fill="#fff"/>
                      <circle cx="7.9" cy="7.7" r="1.2" fill="#fff"/>
                      <path fill="#fff" d="M11.2 9.8h2.3v1.2h.03c.32-.58 1.11-1.34 2.57-1.34 2.75 0 3.25 1.77 3.25 4.07v3.27H17V14.2c0-1.03-.02-2.36-1.44-2.36-1.45 0-1.67 1.13-1.67 2.29v3.85h-2.69V9.8z"/>
                    </svg>
                  </a>
                  {/* YouTube badge */}
                  <a href="#" aria-label="YouTube" onClick={(e)=>e.preventDefault()} className="inline-flex items-center justify-center w-9 h-9 rounded-full shadow-sm transition hover:shadow-md hover:scale-105" title="YouTube">
                    <svg viewBox="0 0 24 24" className="w-9 h-9" aria-hidden="true">
                      <circle cx="12" cy="12" r="12" fill="#FF0000"/>
                      <path d="M10 8.5 16 12l-6 3.5z" fill="#fff"/>
                    </svg>
                  </a>
                  {/* TikTok badge with dual-color accent */}
                  <a href="#" aria-label="TikTok" onClick={(e)=>e.preventDefault()} className="inline-flex items-center justify-center w-9 h-9 rounded-full shadow-sm transition hover:shadow-md hover:scale-105" title="TikTok">
                    <svg viewBox="0 0 24 24" className="w-9 h-9" aria-hidden="true">
                      <circle cx="12" cy="12" r="12" fill="#000000"/>
                      <path d="M14.8 6.5c.66.91 1.76 1.64 3.2 1.81v2.07c-1.42-.03-2.67-.4-3.7-1.05v4.6c0 2.8-2.06 4.34-4.16 4.34-2.25 0-4.14-1.7-4.14-3.93 0-2.24 1.77-3.94 4.02-3.94.4 0 .77.05 1.13.16v2.16a2.1 2.1 0 0 0-1.08-.3 2.03 2.03 0 1 0 2.03 2.03V5.5h2.7z" fill="#69C9D0" opacity=".9"/>
                      <path d="M14.8 6.5c.66.91 1.76 1.64 3.2 1.81v2.07c-1.42-.03-2.67-.4-3.7-1.05v4.6c0 2.8-2.06 4.34-4.16 4.34-2.25 0-4.14-1.7-4.14-3.93 0-2.24 1.77-3.94 4.02-3.94.4 0 .77.05 1.13.16v2.16a2.1 2.1 0 0 0-1.08-.3 2.03 2.03 0 1 0 2.03 2.03V5.5h2.7z" fill="#EE1D52" opacity=".6" transform="translate(.4 .4)"/>
                      <path d="M14.8 6.5c.66.91 1.76 1.64 3.2 1.81v2.07c-1.42-.03-2.67-.4-3.7-1.05v4.6c0 2.8-2.06 4.34-4.16 4.34-2.25 0-4.14-1.7-4.14-3.93 0-2.24 1.77-3.94 4.02-3.94.4 0 .77.05 1.13.16v2.16a2.1 2.1 0 0 0-1.08-.3 2.03 2.03 0 1 0 2.03 2.03V5.5h2.7z" fill="#FFFFFF" opacity=".85"/>
                    </svg>
                  </a>
                </div>
              </div>
            </div>

            {/* Sedes/Contacto */}
            <div className="grid md:grid-cols-3 gap-8 text-sm">
              <div>
                <h4 className="text-white font-semibold mb-2">GUAYAQUIL</h4>
                <p className="text-gray-400">Correo: info@visioncare.ec</p>
                <p className="text-gray-400">Teléfono: 0990000000</p>
                <p className="text-gray-400 mt-2">Letamendi 602 y Noguchi · Guayaquil · Ecuador</p>
              </div>
              <div>
                <h4 className="text-white font-semibold mb-2">QUITO</h4>
                <p className="text-gray-400">Av. Ejemplo N33-155 y Calle Bosmediano</p>
                <p className="text-gray-400">Quito · Ecuador</p>
              </div>
              <div>
                <h4 className="text-white font-semibold mb-2">CONQUENSE</h4>
                <p className="text-gray-400">Juan José Flores 1-38 y Huayna Cápac</p>
                <p className="text-gray-400">Cuenca · Ecuador</p>
              </div>
            </div>

            {/* Links inferiores */}
            <div className="border-t border-white/10 mt-10 pt-4 text-xs text-gray-400 flex flex-wrap gap-x-4 gap-y-2">
              <a href="#" className="hover:text-white" onClick={(e)=>e.preventDefault()}>Inicio</a>
              <a href="#" className="hover:text-white" onClick={(e)=>e.preventDefault()}>Conócenos</a>
              <a href="#" className="hover:text-white" onClick={(e)=>e.preventDefault()}>Servicios</a>
              <a href="#" className="hover:text-white" onClick={(e)=>e.preventDefault()}>Centros</a>
              <a href="#" className="hover:text-white" onClick={(e)=>e.preventDefault()}>Política de datos</a>
              <span className="ml-auto">© {new Date().getFullYear()} VisionCare Web</span>
            </div>
          </div>
        </footer>
      </div>
    );
  }, [user, handleLogout, toast]);

  const DashboardPage = useMemo(() => () => {
    return (
    <div className="min-h-screen bg-gray-50">
      {showWebcam && (
        <WebcamCapture
          onCapture={handleWebcamCapture}
          onClose={() => setShowWebcam(false)}
        />
      )}
      
      <TopNav
        user={user}
        onGoDashboard={() => setCurrentView('start')}
        onGoProfile={() => setCurrentView('profile')}
        onGoChangePassword={() => setCurrentView('change-password')}
        onGoHistory={() => { setCurrentView('history'); loadAnalysisHistory(); }}
        onLogout={() => handleLogout()}
      />

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white/90 backdrop-blur rounded-3xl shadow-xl ring-1 ring-black/5 p-6 md:p-8 transition-all hover:shadow-2xl">
            <h2 className="text-3xl md:text-4xl font-extrabold text-center mb-8 bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-violet-600 to-sky-600 drop-shadow-sm">Análisis de Enfermedades Oculares</h2>
            
            <div className="grid md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-xl font-semibold mb-4">Captura de Imagen del Ojo</h3>
                
                {/* Image capture options */}
                <div className="mb-6">
                  <div className="flex space-x-3 mb-4">
                    <button
                      onClick={() => setCaptureMode('upload')}
                      className={`flex-1 py-2.5 px-4 rounded-xl font-semibold transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 ${
                        captureMode === 'upload'
                          ? 'bg-indigo-600 text-white shadow-md hover:bg-indigo-700'
                          : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
                      }`}
                    >
                      📁 Subir Imagen
                    </button>
                    <button
                      onClick={() => setCaptureMode('webcam')}
                      className={`flex-1 py-2.5 px-4 rounded-xl font-semibold transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2 ${
                        captureMode === 'webcam'
                          ? 'bg-indigo-600 text-white shadow-md hover:bg-indigo-700'
                          : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200'
                      }`}
                    >
                      📷 Usar Cámara
                    </button>
                  </div>
                </div>

                {captureMode === 'upload' ? (
                  <div className="group border-2 border-dashed border-gray-300 hover:border-indigo-400 rounded-2xl p-6 text-center transition-colors bg-white">
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
                      {previewUrl && previewSource === 'upload' ? (
                        <img
                          src={previewUrl}
                          alt="Preview"
                          className="max-w-full max-h-64 mx-auto rounded-xl shadow-md"
                        />
                      ) : (
                        <div>
                          <div className="text-5xl mb-2">📁</div>
                          <p className="text-gray-600 font-medium">Haz clic para seleccionar una imagen</p>
                          <p className="text-sm text-gray-400 mt-2">
                            JPG, PNG hasta 5MB
                          </p>
                        </div>
                      )}
                    </label>
                  </div>
                ) : (
                  <div className="border-2 border-dashed border-indigo-300/70 rounded-2xl p-6 text-center bg-indigo-50">
                    {previewUrl && previewSource === 'webcam' ? (
                      <div>
                        <img
                          src={previewUrl}
                          alt="Captured"
                          className="max-w-full max-h-64 mx-auto rounded-xl mb-4 shadow-md"
                        />
                        <p className="text-sm text-gray-600 mb-4">✅ Imagen capturada correctamente</p>
                        <button
                          onClick={() => setShowWebcam(true)}
                          className="bg-indigo-600 text-white px-4 py-2 rounded-xl hover:bg-indigo-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
                        >
                          📷 Capturar Nueva Foto
                        </button>
                      </div>
                    ) : (
                      <div>
                        <div className="text-4xl mb-2">📷</div>
                        <p className="text-gray-700 font-semibold mb-2">Webcam Capture</p>
                        <p className="text-sm text-gray-600 mb-4">
                          Toma una foto directamente con tu cámara
                        </p>
                        <button
                          onClick={() => setShowWebcam(true)}
                          className="bg-indigo-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-indigo-700 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
                        >
                          📷 Encender Cámara
                        </button>
                      </div>
                    )}
                  </div>
                )}
                
                <button
                  onClick={analyzeImage}
                  disabled={!selectedFile || isAnalyzing}
                  className="w-full mt-4 bg-green-600 text-white p-3 rounded-xl font-semibold hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center space-x-2 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all focus:outline-none focus:ring-2 focus:ring-green-400 focus:ring-offset-2"
                >
                  {isAnalyzing ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                      <span>Analizando...</span>
                    </>
                  ) : (
                    <>
                      <span>🔍</span>
                      <span>Analizar Imagen</span>
                    </>
                  )}
                </button>
              </div>

              <div>
                <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700">⚙️</span>
                  Cómo funciona
                </h3>
                <div className="space-y-4">
                  <p className="text-gray-600 text-sm">
                    Los algoritmos OpenCV mejoran la calidad de la imagen y detectan regiones oculares
                  </p>
                  
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-700 rounded-full w-9 h-9 aspect-square flex items-center justify-center text-base font-extrabold shadow-sm ring-1 ring-indigo-100">
                      3
                    </div>
                    <div>
                      <h4 className="font-semibold">Análisis Médico IA</h4>
                      <p className="text-gray-600 text-sm">
                        Modelos avanzados analizan cataratas y conjuntivitis
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-start space-x-3">
                    <div className="bg-indigo-100 text-indigo-700 rounded-full w-9 h-9 aspect-square flex items-center justify-center text-base font-extrabold shadow-sm ring-1 ring-indigo-100">
                      4
                    </div>
                    <div>
                      <h4 className="font-semibold">Reporte Médico</h4>
                      <p className="text-gray-600 text-sm">
                        Obtén diagnóstico detallado con niveles de confianza y recomendaciones
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-4">
                  <h4 className="font-semibold text-amber-800 mb-2 flex items-center gap-2"><span>📋</span> Mejores Prácticas</h4>
                  <ul className="text-sm text-amber-700 space-y-1">
                    <li>• Asegura buena iluminación en tu ojo</li>
                    <li>• Mantén el ojo bien abierto</li>
                    <li>• Mantén la cámara estable y cercana</li>
                    <li>• Evita reflejos o sombras</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    );
  }, [user, previewUrl, selectedFile, isAnalyzing, captureMode, showWebcam, handleFileSelect, analyzeImage, handleLogout, loadAnalysisHistory, handleWebcamCapture]);

  // Shared TopNav component used across pages
  const TopNav = ({ user, onGoDashboard, onGoProfile, onGoChangePassword, onGoHistory, onLogout }) => {
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef(null);
    const lastOpenedAtRef = useRef(0);
    const triggerRef = useRef(null);
    // null initially to avoid first-frame render at (0,0)
    const [menuCoords, setMenuCoords] = useState(null);

    const computeCoords = useCallback(() => {
      const el = triggerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const menuWidth = 288; // w-72 (18rem)
      const gap = 8; // ~mt-2
      let left = Math.min(
        Math.max(rect.right - menuWidth, 8),
        window.innerWidth - menuWidth - 8
      );
      const top = rect.bottom + gap;
      setMenuCoords({ top, left });
    }, []);

    useEffect(() => {
      const onKey = (e) => {
        if (e.key === 'Escape') setMenuOpen(false);
      };
      document.addEventListener('keydown', onKey);
      return () => {
        document.removeEventListener('keydown', onKey);
      };
    }, []);

    useEffect(() => {
      if (!menuOpen) return;
      computeCoords();
      window.addEventListener('resize', computeCoords);
      // capture scrolls in containers to keep position aligned
      window.addEventListener('scroll', computeCoords, true);
      return () => {
        window.removeEventListener('resize', computeCoords);
        window.removeEventListener('scroll', computeCoords, true);
      };
    }, [menuOpen, computeCoords]);

    return (
      <nav className="bg-white shadow-sm p-4">
        <div className="container mx-auto flex justify-between items-center">
          <button
            type="button"
            onClick={onGoDashboard}
            className="flex items-center gap-2 group"
            title="Ir al panel"
            aria-label="Ir al panel"
          >
            <img
              src="/hero-visioncare.png"
              alt="VisionCare Web"
              className="h-10 md:h-12 w-auto object-contain group-hover:opacity-90 cursor-pointer"
              loading="lazy"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          </button>
          <div className="flex items-center space-x-4">
            <div className="relative flex items-center gap-3" ref={menuRef}>
              {/* Label: Mi perfil (no clickable) */}
              <span
                className="hidden sm:inline-flex items-center text-sm font-medium text-gray-700 px-2 py-1 select-none"
                aria-hidden="true"
              >
                Mi perfil
              </span>
              <button
                type="button"
                onMouseDown={(e) => {
                  // Prevent any outside mousedown listeners from firing
                  e.preventDefault();
                  e.stopPropagation();
                  if (e.nativeEvent && typeof e.nativeEvent.stopImmediatePropagation === 'function') {
                    e.nativeEvent.stopImmediatePropagation();
                  }
                  // Compute coords synchronously and then open to avoid flicker at (0,0)
                  try { (computeCoords)(); } catch {}
                  setMenuOpen(o => {
                    const next = !o;
                    if (next) lastOpenedAtRef.current = Date.now();
                    return next;
                  });
                }}
                onClick={(e) => {
                  // No-op on click to prevent double toggle after mousedown
                  e.preventDefault();
                  e.stopPropagation();
                  if (e.nativeEvent && typeof e.nativeEvent.stopImmediatePropagation === 'function') {
                    e.nativeEvent.stopImmediatePropagation();
                  }
                }}
                ref={triggerRef}
                className="flex items-center focus:outline-none"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                title="Menú de usuario"
              >
                <img
                  src={toAbsoluteUrl(user?.avatar_url) || '/logo-eye.png'}
                  alt="Avatar"
                  className="w-9 h-9 rounded-full object-cover border"
                  onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }}
                />
              </button>
              {menuOpen && menuCoords && createPortal(
                <>
                  {/* Backdrop to handle outside clicks without global listeners; non-focusable to avoid selection loss */}
                  <div
                    role="presentation"
                    tabIndex={-1}
                    aria-hidden="true"
                    style={{ position: 'fixed', inset: 0, zIndex: 999, background: 'transparent', cursor: 'default' }}
                    onMouseDown={(e) => {
                      // Ignore same gesture that opened the menu
                      if (Date.now() - lastOpenedAtRef.current < 120) return;
                      e.stopPropagation();
                      setMenuOpen(false);
                    }}
                  />
                  <div
                    className="w-72 bg-white border border-gray-200 rounded-xl shadow-lg"
                    style={{ position: 'fixed', top: menuCoords.top, left: menuCoords.left, zIndex: 1000 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="p-4 border-b">
                      <div className="flex items-center gap-3">
                        <img
                          src={toAbsoluteUrl(user?.avatar_url) || '/logo-eye.png'}
                          alt="Avatar"
                          className="w-10 h-10 rounded-full object-cover border"
                          onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }}
                        />
                        <div className="min-w-0">
                          <div className="font-semibold truncate">{`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'Usuario'}</div>
                          <div className="text-xs text-gray-500 truncate">{user?.email}</div>
                        </div>
                      </div>
                    </div>
                    <div className="p-2">
                      <button onClick={() => { onGoProfile(); setMenuOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100">Gestionar mi perfil</button>
                      <button onClick={() => { onGoChangePassword(); setMenuOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100">Cambiar contraseña</button>
                      <button onClick={() => { onGoHistory(); setMenuOpen(false); }} className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-100">Historial</button>
                    </div>
                    <div className="p-2 border-t">
                      <button onClick={() => { setMenuOpen(false); onLogout(); }} className="w-full text-left px-3 py-2 rounded-lg text-red-600 hover:bg-red-50">Cerrar sesión</button>
                    </div>
                  </div>
                </>,
                document.body
              )}
            </div>
          </div>
        </div>
      </nav>
    );
  };

  // Profile Page (view/update profile only)
  const ProfilePage = useMemo(() => () => {
    const [profile, setProfile] = useState(user || {});
    const [saving, setSaving] = useState(false);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);
    const [activeSection, setActiveSection] = useState('personales');
    const [editMode, setEditMode] = useState(false);
  const [openAcc, setOpenAcc] = useState({ personal: true, medica: true });
    const avatarInputRef = useRef(null);
    // Dependent selects state (ISO codes) for edit mode
    const [pCountryCode, setPCountryCode] = useState('');
    const [pStateCode, setPStateCode] = useState('');
    const [pCityName, setPCityName] = useState('');
    const countriesList = useMemo(() => Country.getAllCountries(), []);
    const statesList = useMemo(() => (pCountryCode ? State.getStatesOfCountry(pCountryCode) : []), [pCountryCode]);
    const citiesList = useMemo(() => (pCountryCode && pStateCode) ? City.getCitiesOfState(pCountryCode, pStateCode) : [], [pCountryCode, pStateCode]);

    // Initialize codes from current profile when entering edit mode
    useEffect(() => {
      if (!editMode) return;
      try {
        let cCode = pCountryCode;
        if (!cCode && profile?.country) {
          const c = countriesList.find(x => (x.name || '').toLowerCase() === (profile.country || '').toLowerCase());
          cCode = c?.isoCode || '';
        }
        let sCode = pStateCode;
        if (cCode && profile?.state) {
          const st = State.getStatesOfCountry(cCode);
          const s = st.find(x => (x.name || '').toLowerCase() === (profile.state || '').toLowerCase());
          sCode = s?.isoCode || '';
        }
        const city = pCityName || profile?.city || '';
        if (cCode !== pCountryCode) setPCountryCode(cCode);
        if (sCode !== pStateCode) setPStateCode(sCode);
        if (city !== pCityName) setPCityName(city);
      } catch {}
    }, [editMode, profile, countriesList, pCountryCode, pStateCode, pCityName]);

    useEffect(() => {
      // Load latest profile from API
      (async () => {
        try {
          const { data } = await axios.get(`${API}/auth/profile/`);
          setProfile(data);
        } catch (e) {
          console.error('Load profile failed', e?.response || e);
        }
      })();
    }, []);

    const saveProfile = async () => {
      try {
        setSaving(true);
        const countryName = pCountryCode ? (Country.getCountryByCode(pCountryCode)?.name || '') : (profile.country || '');
        const stateName = (pCountryCode && pStateCode) ? (State.getStateByCodeAndCountry(pStateCode, pCountryCode)?.name || '') : (profile.state || '');
        const cityName = pCityName || profile.city || '';
        const payload = {
          email: profile.email || '',
          username: profile.username || '',
          first_name: profile.first_name || '',
          last_name: profile.last_name || '',
          phone: profile.phone || '',
          address: profile.address || '',
          country: countryName,
          state: stateName,
          city: cityName,
          age: profile.age || null,
          gender: profile.gender || 'na',
          cedula: profile.cedula || '',
          blood_type: profile.blood_type || null,
          weight_kg: profile.weight_kg || null,
          height_m: profile.height_m || null,
        };
  const { data } = await axios.put(`${API}/auth/profile/`, payload);
  setProfile(data);
  if (typeof setUser === 'function') setUser(u => (u ? { ...u, email: data.email, username: data.username, first_name: data.first_name, last_name: data.last_name } : u));
  toast({ title: 'Perfil actualizado', description: 'Tus cambios se guardaron correctamente.' });
        setEditMode(false);
      } catch (e) {
        const msg = e?.response?.data ? JSON.stringify(e.response.data) : 'Error al actualizar';
  toast({ title: 'Error al actualizar', description: msg, variant: 'destructive' });
      } finally {
        setSaving(false);
      }
    };

    const handleSelectAvatar = async (file) => {
      if (!file) return;
      try {
        setUploadingAvatar(true);
        const fd = new FormData();
        fd.append('avatar', file);
        const { data } = await axios.post(`${API}/auth/avatar/`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
        setProfile(p => ({ ...p, avatar_url: data.avatar_url }));
        if (typeof setUser === 'function') setUser(u => (u ? { ...u, avatar_url: data.avatar_url } : u));
      } catch (e) {
        const d = e?.response?.data; const msg = typeof d === 'string' ? d : (d ? JSON.stringify(d) : 'Error al subir avatar');
  toast({ title: 'Error al subir avatar', description: msg, variant: 'destructive' });
      } finally {
        setUploadingAvatar(false);
        if (avatarInputRef.current) avatarInputRef.current.value = '';
      }
    };

    return (
      <div className="min-h-screen bg-gray-50">
        <TopNav
          user={user}
          onGoDashboard={() => setCurrentView('dashboard')}
          onGoProfile={() => setCurrentView('profile')}
          onGoChangePassword={() => setCurrentView('change-password')}
          onGoHistory={() => { setCurrentView('history'); loadAnalysisHistory(); }}
          onLogout={() => handleLogout()}
        />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar - Accordion */}
            <aside className="bg-white rounded-lg shadow p-0 lg:col-span-1 h-max overflow-hidden">
              {/* Información personal */}
              <div className="border-b">
                <button onClick={() => setOpenAcc(s => ({ ...s, personal: !s.personal }))} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50">
                  <span className="font-semibold">Información personal</span>
                  <span className="text-gray-500">{openAcc.personal ? '▾' : '▸'}</span>
                </button>
                {openAcc.personal && (
                  <nav className="px-2 pb-3 space-y-1">
                    <button onClick={() => setActiveSection('personales')} className={`w-full text-left px-3 py-2 rounded ${activeSection==='personales'?'bg-indigo-50 text-indigo-700':'hover:bg-gray-50'}`}>Datos personales</button>
                  </nav>
                )}
              </div>

              {/* Información médica */}
              <div className="border-b">
                <button onClick={() => setOpenAcc(s => ({ ...s, medica: !s.medica }))} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50">
                  <span className="font-semibold">Información médica</span>
                  <span className="text-gray-500">{openAcc.medica ? '▾' : '▸'}</span>
                </button>
                {openAcc.medica && (
                  <nav className="px-2 pb-3 space-y-1">
                    <button onClick={() => setActiveSection('medica')} className={`w-full text-left px-3 py-2 rounded ${activeSection==='medica'?'bg-indigo-50 text-indigo-700':'hover:bg-gray-50'}`}>Datos médicos</button>
                  </nav>
                )}
              </div>

              {/* Removed other sections per request */}
            </aside>

            {/* Main panel */}
            <main className="lg:col-span-3 space-y-6">
              <div className="bg-white rounded-lg shadow p-6">
                {/* Title header */}
                <div className="flex items-center justify-between pb-4 mb-6 border-b">
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-6 bg-yellow-500 rounded" />
                    <h2 className="text-2xl font-bold">{activeSection==='medica' ? 'Datos médicos' : 'Datos personales'}</h2>
                  </div>
                  {!editMode && (
                    <button onClick={() => setEditMode(true)} className="px-4 h-10 rounded bg-slate-200 hover:bg-slate-300 text-slate-800">Editar</button>
                  )}
                </div>

                {/* Avatar header - only in Datos personales */}
                {activeSection === 'personales' && (
                  <div className="flex items-center justify-between pb-4 mb-6">
                    <div className="flex items-center gap-4 min-w-0">
                      <img src={toAbsoluteUrl(profile.avatar_url) || '/logo-eye.png'} alt="Avatar" className="w-20 h-20 rounded-full object-cover border" onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }} />
                      <div className="min-w-0">
                        <div className="font-semibold">Tu foto de perfil</div>
                        <div className="text-xs text-gray-500 truncate">Máximo 5MB · JPG, PNG, WEBP, GIF</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <input ref={avatarInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleSelectAvatar(e.target.files?.[0])} />
                      <button
                        disabled={uploadingAvatar}
                        onClick={() => avatarInputRef.current?.click()}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-60 whitespace-nowrap shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 transition"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M3 16.5V19.5C3 20.328 3.672 21 4.5 21H19.5C20.328 21 21 20.328 21 19.5V16.5"/>
                          <path d="M7.5 12L12 7.5L16.5 12"/>
                          <path d="M12 7.5V18"/>
                        </svg>
                        <span className="text-sm font-medium">{uploadingAvatar ? 'Actualizando…' : 'Actualizar foto'}</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Section content */}
                {activeSection === 'personales' && (
                  <div className="space-y-6">
                    {!editMode ? (
                      <div className="grid md:grid-cols-3 gap-y-4 gap-x-8 text-sm">
                        <div>
                          <div className="text-gray-500">Nombres:</div>
                          <div className="font-semibold uppercase">{profile.first_name || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Apellidos:</div>
                          <div className="font-semibold uppercase">{profile.last_name || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Usuario:</div>
                          <div className="font-semibold">{profile.username || 'S/N'}</div>
                        </div>

                        <div>
                          <div className="text-gray-500">CÉDULA:</div>
                          <div className="font-semibold">{profile.cedula || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Edad:</div>
                          <div className="font-semibold">{profile.age ?? 'S/N'}</div>
                        </div>
                        {/* Removed Fecha de nacimiento and Estado civil per request */}

                        <div>
                          <div className="text-gray-500">País de nacionalidad:</div>
                          <div className="font-semibold uppercase">{profile.country || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Estado/Provincia:</div>
                          <div className="font-semibold uppercase">{profile.state || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Ciudad:</div>
                          <div className="font-semibold uppercase">{profile.city || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Género:</div>
                          <div className="font-semibold uppercase">{(profile.gender || 'S/N').toString()}</div>
                        </div>
                        <div>
                          <div className="text-gray-500">Correo electrónico personal:</div>
                          <div className="font-semibold break-all">{profile.email || 'S/N'}</div>
                        </div>

                        <div>
                          <div className="text-gray-500">Teléfono:</div>
                          <div className="font-semibold">{profile.phone || 'S/N'}</div>
                        </div>
                        <div className="md:col-span-2">
                          <div className="text-gray-500">Dirección:</div>
                          <div className="font-semibold break-words">{profile.address || 'S/N'}</div>
                        </div>
                        {/* Removed Persona zurda, Discapacidad, Certificado de votación per request */}
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="grid md:grid-cols-3 gap-3">
                          <div className="md:col-span-1">
                            <label className="block text-sm text-gray-700 mb-1">Nombres</label>
                            <input value={profile.first_name || ''} onChange={e => setProfile(p => ({ ...p, first_name: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                          <div className="md:col-span-1">
                            <label className="block text-sm text-gray-700 mb-1">Apellidos</label>
                            <input value={profile.last_name || ''} onChange={e => setProfile(p => ({ ...p, last_name: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                          <div className="md:col-span-1">
                            <label className="block text-sm text-gray-700 mb-1">Usuario</label>
                            <input value={profile.username || ''} onChange={e => setProfile(p => ({ ...p, username: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                        </div>
                        <div className="grid md:grid-cols-3 gap-3">
                          <div className="md:col-span-1">
                            <label className="block text-sm text-gray-700 mb-1">Correo electrónico personal</label>
                            <input type="email" value={profile.email || ''} onChange={e => setProfile(p => ({ ...p, email: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                        </div>
                        <div className="grid md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Cédula</label>
                            <input value={profile.cedula || ''} disabled className="w-full h-10 border border-gray-300 rounded px-3 bg-gray-100" />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Edad</label>
                            <input type="number" min="1" max="120" value={profile.age ?? ''} onChange={e => setProfile(p => ({ ...p, age: e.target.value ? parseInt(e.target.value, 10) : null }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Género</label>
                            <select value={profile.gender || 'na'} onChange={e => setProfile(p => ({ ...p, gender: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3 bg-white">
                              <option value="na">Prefiero no decir</option>
                              <option value="male">Masculino</option>
                              <option value="female">Femenino</option>
                              <option value="other">Otro</option>
                            </select>
                          </div>
                        </div>
                        <div className="grid md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Teléfono</label>
                            <div className="[&_.PhoneInput]:w-full">
                              <PhoneInput
                                international
                                key={pCountryCode}
                                defaultCountry={pCountryCode || 'EC'}
                                flags={FLAG_ICONS}
                                placeholder="Ingresa tu número"
                                value={profile.phone || ''}
                                onChange={(value) => setProfile(p => ({ ...p, phone: value || '' }))}
                                className="PhoneInput w-full"
                              />
                            </div>
                          </div>
                          <div className="md:col-span-2">
                            <label className="block text-sm text-gray-700 mb-1">Dirección</label>
                            <input value={profile.address || ''} onChange={e => setProfile(p => ({ ...p, address: e.target.value }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                        </div>
                        <div className="grid md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">País</label>
                            <CountryDropdown
                              value={pCountryCode}
                              countries={countriesList}
                              disabled={false}
                              hasError={false}
                              onChange={(countryCode) => {
                                defer(() => {
                                  setPCountryCode(countryCode);
                                  setPStateCode('');
                                  setPCityName('');
                                });
                              }}
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Estado/Provincia</label>
                            <select
                              key={`pstate-${pCountryCode}`}
                              value={pStateCode}
                              onChange={(e) => {
                                const value = e.target.value;
                                if (e.target && typeof e.target.blur === 'function') e.target.blur();
                                defer(() => {
                                  setPStateCode(value);
                                  setPCityName('');
                                });
                              }}
                              className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                              disabled={!pCountryCode || statesList.length === 0}
                            >
                              <option value="">{statesList.length ? 'Seleccione una provincia/estado' : 'No hay datos'}</option>
                              {statesList.map(s => (
                                <option key={`${s.countryCode}-${s.isoCode}`} value={s.isoCode}>{s.name}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Ciudad</label>
                            <select
                              key={`pcity-${pStateCode}`}
                              value={pCityName}
                              onChange={(e) => {
                                const value = e.target.value;
                                if (e.target && typeof e.target.blur === 'function') e.target.blur();
                                defer(() => {
                                  setPCityName(value);
                                });
                              }}
                              className="w-full h-11 px-4 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                              disabled={!pStateCode || citiesList.length === 0}
                            >
                              <option value="">{citiesList.length ? 'Seleccione una ciudad' : 'No hay datos'}</option>
                              {citiesList.map(city => (
                                <option key={`${city.name}-${city.stateCode}-${city.countryCode}`} value={city.name}>{city.name}</option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="pt-2 flex gap-3">
                          <button disabled={saving} onClick={saveProfile} className="flex-1 bg-indigo-600 text-white h-10 rounded hover:bg-indigo-700">{saving ? 'Guardando...' : 'Guardar cambios'}</button>
                          <button type="button" onClick={() => setEditMode(false)} className="px-4 h-10 rounded bg-slate-200 hover:bg-slate-300 text-slate-800">Cancelar</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeSection === 'medica' && (
                  <div className="space-y-6">
                    {/* Header card with avatar + identity */}
                    <div className="flex items-start gap-6 pb-6 border-b">
                      <img src={toAbsoluteUrl(profile.avatar_url) || '/logo-eye.png'} alt="Avatar" className="w-28 h-28 rounded-full object-cover border" onError={(e) => { e.currentTarget.src = '/logo-eye.png'; }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-2xl md:text-3xl font-extrabold tracking-wide uppercase text-slate-800 truncate">
                          {(profile.first_name || '') + ' ' + (profile.last_name || '')}
                        </div>
                        <div className="mt-4 grid sm:grid-cols-[auto,1fr] gap-x-6 gap-y-2 text-slate-700">
                          <div className="font-semibold">Cédula</div>
                          <div className="text-slate-600">{profile.cedula || 'S/N'}</div>
                          <div className="font-semibold">Email</div>
                          <div className="text-slate-600 break-all">{profile.email || 'S/N'}</div>
                        </div>
                      </div>
                    </div>

                    {!editMode ? (
                      <div className="grid md:grid-cols-3 gap-y-4 gap-x-8 text-center">
                        <div>
                          <div className="text-gray-500 font-semibold">Tipo de sangre</div>
                          <div className="text-3xl font-semibold mt-1">{profile.blood_type || 'S/N'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500 font-semibold">Peso (Kg)</div>
                          <div className="text-3xl font-semibold mt-1">{profile.weight_kg ?? '0'}</div>
                        </div>
                        <div>
                          <div className="text-gray-500 font-semibold">Estatura (Mts)</div>
                          <div className="text-3xl font-semibold mt-1">{profile.height_m ?? '0'}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="grid md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Tipo de sangre</label>
                            <select value={profile.blood_type || ''} onChange={e => setProfile(p => ({ ...p, blood_type: e.target.value || null }))} className="w-full h-10 border border-gray-300 rounded px-3 bg-white">
                              <option value="">S/N</option>
                              {['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(bt => (
                                <option key={bt} value={bt}>{bt}</option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Peso (Kg)</label>
                            <input type="number" step="0.01" min="0" max="500" value={profile.weight_kg ?? ''} onChange={e => setProfile(p => ({ ...p, weight_kg: e.target.value ? parseFloat(e.target.value) : null }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-700 mb-1">Estatura (Mts)</label>
                            <input type="number" step="0.01" min="0" max="3" value={profile.height_m ?? ''} onChange={e => setProfile(p => ({ ...p, height_m: e.target.value ? parseFloat(e.target.value) : null }))} className="w-full h-10 border border-gray-300 rounded px-3" />
                          </div>
                        </div>
                        <div className="pt-2 flex gap-3">
                          <button disabled={saving} onClick={saveProfile} className="flex-1 bg-indigo-600 text-white h-10 rounded hover:bg-indigo-700">{saving ? 'Guardando...' : 'Guardar cambios'}</button>
                          <button type="button" onClick={() => setEditMode(false)} className="px-4 h-10 rounded bg-slate-200 hover:bg-slate-300 text-slate-800">Cancelar</button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

              </div>
            </main>
          </div>
        </div>
      </div>
    );
  }, [user, handleLogout]);

  // Change Password Page (only password form)
  const ChangePasswordPage = useMemo(() => () => {
    const [pwd, setPwd] = useState({ old_password: '', new_password: '', new_password_confirm: '' });
    const [saving, setSaving] = useState(false);

    // Client-side validation rules for new password
    const rules = useMemo(() => {
      const op = pwd.old_password || '';
      const np = pwd.new_password || '';
      const cp = pwd.new_password_confirm || '';
      const hasOld = op.length > 0;
      const different = !!np && !!op && np !== op;
      const hasLetter = /[A-Za-z]/.test(np);
      const hasUpperLower = /[A-Z]/.test(np) && /[a-z]/.test(np);
      const hasNumber = /\d/.test(np);
      const minLen = (np.length || 0) >= 8;
      const confirmMatch = !!np && !!cp && np === cp;
      const isValid = hasOld && different && hasLetter && hasUpperLower && hasNumber && minLen && confirmMatch;
      return { hasOld, different, hasLetter, hasUpperLower, hasNumber, minLen, confirmMatch, isValid };
    }, [pwd]);

    const changePassword = async () => {
      try {
        setSaving(true);
        if (!rules.isValid) {
  toast({ title: 'Revisa los requisitos', description: 'Completa correctamente los campos de contraseña.', variant: 'destructive' });
          return;
        }
        await axios.post(`${API}/auth/change-password/`, pwd);
  toast({ title: 'Contraseña actualizada', description: 'Tu contraseña fue cambiada correctamente.' });
        setPwd({ old_password: '', new_password: '', new_password_confirm: '' });
      } catch (e) {
        let msg = 'Error al cambiar contraseña';
        const d = e?.response?.data;
        if (typeof d === 'string') msg = d; else if (d) msg = JSON.stringify(d);
  toast({ title: 'Error al cambiar contraseña', description: msg, variant: 'destructive' });
      } finally {
        setSaving(false);
      }
    };

    return (
      <div className="min-h-screen bg-gray-50">
        <TopNav
          user={user}
          onGoDashboard={() => setCurrentView('dashboard')}
          onGoProfile={() => setCurrentView('profile')}
          onGoChangePassword={() => setCurrentView('change-password')}
          onGoHistory={() => { setCurrentView('history'); loadAnalysisHistory(); }}
          onLogout={() => handleLogout()}
        />
        <div className="container mx-auto px-3 py-6">
          <div className="max-w-2xl mx-auto bg-white rounded-lg shadow p-4">
            <h2 className="text-xl font-semibold mb-4">Cambiar contraseña</h2>
            {/* Password requirements block */}
            <div className="mb-4">
              <div className="flex items-start gap-2">
                <div className="mt-0.5 flex-shrink-0 h-5 w-5 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs">i</div>
                <div>
                  <p className="text-gray-700 font-medium mb-1">La contraseña debe cumplir con los siguientes parámetros:</p>
                  <ul className="list-disc pl-5 space-y-0.5 text-gray-600 text-sm">

                    <li><span className="font-semibold">Contraseña actual debe ser diferente a la contraseña nueva</span></li>
                    <li>Al menos <span className="font-semibold">una letra</span></li>
                    <li>Al menos <span className="font-semibold">una letra en mayúscula y una letra en minúscula</span></li>
                    <li>Al menos <span className="font-semibold">un número</span></li>
                    <li>Al menos ha de contener <span className="font-semibold">8 caracteres</span></li>
                    <li>La nueva contraseña <span className="font-semibold">debe ser igual</span> confirmar contraseña.</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <div>
                <label className="block text-sm text-gray-700 mb-0.5">Contraseña actual</label>
                <input type="password" value={pwd.old_password} onChange={e => setPwd(p => ({ ...p, old_password: e.target.value }))} className="w-full h-9 border border-gray-300 rounded px-3" />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-0.5">Nueva contraseña</label>
                <input type="password" value={pwd.new_password} onChange={e => setPwd(p => ({ ...p, new_password: e.target.value }))} className="w-full h-9 border border-gray-300 rounded px-3" />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-0.5">Confirmar nueva contraseña</label>
                <input type="password" value={pwd.new_password_confirm} onChange={e => setPwd(p => ({ ...p, new_password_confirm: e.target.value }))} className="w-full h-9 border border-gray-300 rounded px-3" />
              </div>
              {!rules.isValid && (
                <p className="text-center text-xs text-yellow-600 font-semibold">Complete los campos de contraseña</p>
              )}
              <button disabled={saving || !rules.isValid} onClick={changePassword} className="w-full bg-green-600 text-white h-9 rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-sm">
                {saving ? 'Actualizando...' : 'Actualizar contraseña'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }, [user, handleLogout, loadAnalysisHistory]);

  // Results Page
  const ResultsPage = useMemo(() => () => (
    <div className="min-h-screen bg-gray-50">
      <TopNav
        user={user}
        onGoDashboard={() => setCurrentView('dashboard')}
        onGoProfile={() => setCurrentView('profile')}
        onGoChangePassword={() => setCurrentView('change-password')}
        onGoHistory={() => { setCurrentView('history'); loadAnalysisHistory(); }}
        onLogout={() => handleLogout()}
      />

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-5xl mx-auto">
          <div className="bg-white rounded-xl shadow-lg p-6 md:p-8">
            {/* Header actions */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
              <h2 className="text-2xl md:text-3xl font-bold tracking-tight flex-1">Resultados del análisis</h2>
              <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                {analysisResult && (
                  <button
                    onClick={() => downloadAnalysisPDF(analysisResult.id)}
                    className="flex-1 sm:flex-none bg-red-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center justify-center gap-2 text-sm"
                  >
                    <span>📄</span>
                    <span>Descargar PDF</span>
                  </button>
                )}
                <button
                  onClick={handleNewDiagnosis}
                  className="flex-1 sm:flex-none bg-indigo-600 text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-indigo-700 transition-colors text-sm"
                >
                  Nuevo diagnóstico
                </button>
              </div>
            </div>

            {!analysisResult && (
              <div className="text-center py-24">
                <p className="text-gray-500 mb-6">No hay un resultado cargado en este momento.</p>
                <button
                  onClick={() => setCurrentView('dashboard')}
                  className="bg-indigo-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-indigo-700"
                >
                  Ir al panel para analizar
                </button>
              </div>
            )}

            {analysisResult && (
              <div className="grid lg:grid-cols-2 gap-8">
                {/* Columna izquierda: Imagen + Indicadores */}
                <div className="space-y-8">
                  <div>
                    <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                      <span>📷</span> <span>Imagen analizada</span>
                    </h3>
                    {(() => {
                      const processedUrlRaw = analysisExtras?.processed_image_url || analysisResult?.ai_raw_response?.processed_image_url;
                      const processedUrl = toAbsoluteUrl(processedUrlRaw);
                      const url = processedUrl || toAbsoluteUrl(analysisResult?.image_url);
                      if (url) {
                        return (
                          <div className="relative">
                            <img
                              src={url}
                              alt={processedUrl ? 'Imagen procesada' : 'Imagen original'}
                              className="w-full rounded-lg shadow-md ring-1 ring-gray-200"
                              loading="lazy"
                              decoding="async"
                            />
                            {processedUrl && (
                              <span className="absolute top-2 left-2 text-[11px] bg-sky-600 text-white px-2 py-0.5 rounded-full shadow">Procesada</span>
                            )}
                          </div>
                        );
                      }
                      return (
                        <div className="w-full h-64 bg-gray-200 rounded-lg flex items-center justify-center">
                          <span className="text-gray-500">Imagen no disponible</span>
                        </div>
                      );
                    })()}
                  </div>

                  <div>
                    <h4 className="font-semibold mb-3">Indicadores (OpenCV / ONNX)</h4>
                    <div className="space-y-3">
                      {analysisResult.ai_raw_response?.onnx && typeof analysisResult.ai_raw_response.onnx.cataracts === 'number' && (
                        <MetricBar label="P(cataratas) [ONNX]" value={analysisResult.ai_raw_response.onnx.cataracts} colorFrom="#06b6d4" colorTo="#0ea5e9" />
                      )}
                      <MetricBar label="Rojez (OpenCV)" value={analysisResult.opencv_redness_score} colorFrom="#ef4444" colorTo="#f97316" />
                      <MetricBar label="Opacidad (OpenCV)" value={analysisResult.opencv_opacity_score} colorFrom="#8b5cf6" colorTo="#06b6d4" />
                      {typeof analysisResult.opencv_vascular_density === 'number' && (
                        <MetricBar label="Densidad vascular" value={analysisResult.opencv_vascular_density} colorFrom="#16a34a" colorTo="#22c55e" />
                      )}
                      <div className="flex items-center justify-between text-sm pt-1">
                        <span className="text-gray-700">Severidad</span>
                        <span className="font-semibold">{SEVERITY_ES[analysisResult.severity?.toLowerCase?.()] || analysisResult.severity}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Columna derecha: Diagnóstico y métricas complementarias */}
                <div className="space-y-8">
                  <div className="bg-gray-50 p-6 rounded-lg border border-gray-100">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
                      <div className="flex items-start gap-3">
                        <div className="text-4xl leading-none">{getDiagnosisIcon(analysisResult.diagnosis)}</div>
                        <div>
                          <h4 className={`text-2xl font-bold ${getDiagnosisColor(analysisResult.diagnosis)}`}>
                            {DIAGNOSIS_ES[analysisResult.diagnosis?.toLowerCase?.()] || analysisResult.diagnosis}
                          </h4>
                          <p className="text-gray-600 text-sm font-medium">
                            Confianza del modelo: {(analysisResult.confidence_score * 100).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                      {analysisResult.ai_raw_response?.onnx && typeof analysisResult.ai_raw_response.onnx.cataracts === 'number' && (
                        <div className="flex-shrink-0 self-center sm:self-start">
                          <Gauge
                            label="P(cataratas)"
                            value={analysisResult.ai_raw_response.onnx.cataracts}
                            size={110}
                            strokeWidth={12}
                            color="#0ea5e9"
                          />
                        </div>
                      )}
                    </div>

                    {(() => {
                      const coTop = analysisExtras?.co_findings;
                      const coRaw = analysisResult?.ai_raw_response?.co_findings;
                      const co = Array.isArray(coTop) && coTop.length ? coTop : (Array.isArray(coRaw) ? coRaw : []);
                      if (!co || co.length === 0) return null;
                      return (
                        <div className="mb-5">
                          <h5 className="font-semibold text-sm tracking-wide text-gray-700">Co-hallazgos</h5>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {co.slice(0,4).map((c, idx) => {
                              const lvl = (c.level || '').toLowerCase();
                              const color = lvl === 'likely' ? 'bg-amber-100 text-amber-800' : 'bg-sky-100 text-sky-800';
                              const label = (c.label === 'cataracts') ? 'Cataratas' : (c.label === 'conjunctivitis' ? 'Conjuntivitis' : String(c.label || ''));
                              const lvlText = (lvl === 'likely') ? 'probable' : 'posible';
                              return (
                                <span key={idx} className={`text-xs px-2 py-1 rounded-full ${color}`}>{label} — {lvlText}</span>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })()}

                    {analysisResult.ai_analysis_text && (
                      <div className="mb-4">
                        <h5 className="font-semibold text-sm text-gray-700 mb-1">Análisis de IA</h5>
                        <p className="text-gray-600 text-sm leading-relaxed">{analysisResult.ai_analysis_text}</p>
                      </div>
                    )}
                    {analysisResult.recommendations && (
                      <div className="mb-4">
                        <h5 className="font-semibold text-sm text-gray-700 mb-1">Recomendaciones</h5>
                        <p className="text-gray-600 text-sm leading-relaxed">{analysisResult.recommendations}</p>
                      </div>
                    )}
                    {analysisResult.medical_advice && (
                      <div className="mb-2">
                        <h5 className="font-semibold text-sm text-gray-700 mb-1">Consejo médico</h5>
                        <p className="text-gray-600 text-sm leading-relaxed">{analysisResult.medical_advice}</p>
                      </div>
                    )}
                    <p className="text-xs text-gray-400 mt-4">Este resultado es generado por IA y no reemplaza una evaluación médica profesional.</p>
                  </div>

                  {(analysisExtras?.quality || analysisExtras?.uncertainty || analysisExtras?.runtime) && (
                    <div>
                      <h4 className="font-semibold mb-3">Métricas del modelo</h4>
                      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
                        {analysisExtras?.quality && (
                          <div className={`rounded-lg border p-4 ${analysisExtras.quality.quality_flag === 'low' ? 'border-amber-300 bg-amber-50' : 'border-green-200 bg-green-50'}`}>
                            <div className="flex items-center justify-between mb-1">
                              <div className="font-semibold text-sm">Calidad de imagen</div>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full ${analysisExtras.quality.quality_flag === 'low' ? 'bg-amber-200 text-amber-800' : 'bg-green-200 text-green-800'}`}>
                                {analysisExtras.quality.quality_flag === 'low' ? 'Baja' : 'Buena'}
                              </span>
                            </div>
                            <MetricBar label="Score" value={Number(analysisExtras.quality.quality_score || 0)} colorFrom="#22c55e" colorTo="#16a34a" />
                            <div className="mt-1 text-[10px] text-gray-600 leading-tight">
                              Brillo: {Math.round((analysisExtras.quality.mean_brightness||0)*100)}% · Osc: {Math.round((analysisExtras.quality.dark_ratio||0)*100)}% · Brill: {Math.round((analysisExtras.quality.bright_ratio||0)*100)}%
                            </div>
                          </div>
                        )}
                        {analysisExtras?.uncertainty && (() => {
                          const UL = getUncertaintyLabel(analysisExtras.uncertainty);
                          return (
                            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
                              <div className="flex items-center justify-between mb-1">
                                <div className="font-semibold text-sm">Consistencia (TTA)</div>
                                {UL && <span className={`text-[10px] px-2 py-0.5 rounded-full ${UL.bg} ${UL.color}`}>{UL.label}</span>}
                              </div>
                              <Gauge label="Top prob" value={Number(analysisExtras.uncertainty.mean_top_prob || 0)} size={90} strokeWidth={11} color="#6366f1" />
                              <div className="mt-1">
                                <MetricBar
                                  label="Entropía"
                                  value={(() => {
                                    const u = analysisExtras?.uncertainty;
                                    if (u && typeof u.entropy_normalized === 'number') {
                                      return Math.min(1, Math.max(0, Number(u.entropy_normalized)));
                                    }
                                    const cls = analysisExtras?.runtime?.class_names?.length || 3;
                                    const maxEnt = Math.log(cls || 3) || 1;
                                    const ent = Number(u?.entropy || 0);
                                    return Math.min(1, Math.max(0, ent / maxEnt));
                                  })()}
                                  colorFrom="#93c5fd"
                                  colorTo="#1d4ed8"
                                />
                              </div>
                            </div>
                          );
                        })()}
                        {analysisExtras?.runtime && (
                          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                            <div className="font-semibold text-sm mb-1">Ejecución</div>
                            <div className="text-xs text-slate-700">Modelos: {analysisExtras.runtime.model_count ?? 0}</div>
                            {Array.isArray(analysisExtras.runtime.providers) && analysisExtras.runtime.providers.length > 0 && (
                              <div className="text-[10px] text-slate-600 mt-1 leading-snug">Providers: {analysisExtras.runtime.providers.join(', ')}</div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ), [analysisResult, analysisExtras, getDiagnosisIcon, getDiagnosisColor, handleLogout, loadAnalysisHistory, downloadAnalysisPDF, getUncertaintyLabel, handleNewDiagnosis]);

  // History Page
  const HistoryPage = useMemo(() => () => (
    <div className="min-h-screen bg-gray-50">
      <TopNav
        user={user}
        onGoDashboard={() => setCurrentView('dashboard')}
        onGoProfile={() => setCurrentView('profile')}
        onGoChangePassword={() => setCurrentView('change-password')}
        onGoHistory={() => { setCurrentView('history'); loadAnalysisHistory(); }}
        onLogout={() => handleLogout()}
      />

      <div className="container mx-auto px-4 py-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8 flex items-center justify-between gap-4">
            <h2 className="text-3xl font-bold">Historial de análisis</h2>
            {analysisHistory.length > 0 && (
              <button
                onClick={clearHistory}
                className="inline-flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-lg border border-gray-200"
                disabled={historyLoading}
                title="Borrar todo mi historial"
              >
                🗑️ <span>{historyLoading ? 'Borrando…' : 'Borrar historial'}</span>
              </button>
            )}
          </div>
          
          {analysisHistory.length === 0 ? (
            <div className="bg-white rounded-lg shadow-lg p-8 text-center">
              <p className="text-gray-500 text-lg">No hay historial de análisis encontrado</p>
              <button
                onClick={() => setCurrentView('dashboard')}
                className="mt-4 bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700"
              >
                Iniciar tu primer análisis
              </button>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {analysisHistory.map((analysis, index) => (
                <div key={analysis.id} className="bg-white rounded-lg shadow-lg p-6">
                  {analysis.image_url ? (
                    <img
                      src={toAbsoluteUrl(analysis.image_url)}
                      alt="Miniatura del análisis"
                      loading="lazy"
                      className="w-full h-32 object-cover rounded-lg mb-4 bg-gray-100"
                      onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.parentElement?.querySelector?.('.thumb-fallback')?.classList?.remove('hidden'); }}
                    />
                  ) : (
                    <div className="w-full h-32 bg-gray-200 rounded-lg mb-4 flex items-center justify-center">
                      <span className="text-gray-400">No image</span>
                    </div>
                  )}
                  {/* Fallback placeholder kept hidden until onError */}
                  <div className="thumb-fallback hidden w-full h-32 bg-gray-200 rounded-lg mb-4 flex items-center justify-center">
                    <span className="text-gray-400">Miniatura no disponible</span>
                  </div>
                  
                  <div className="flex items-center mb-2">
                    <span className="text-xl mr-2">{getDiagnosisIcon(analysis.diagnosis)}</span>
                    <h3 className={`font-bold ${getDiagnosisColor(analysis.diagnosis)}`}>
                      {DIAGNOSIS_ES[analysis.diagnosis?.toLowerCase?.()] || analysis.diagnosis}
                    </h3>
                  </div>
                  
                  <p className="text-gray-600 text-sm mb-2">
                    Confianza: {(analysis.confidence_score * 100).toFixed(1)}%
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
  ), [analysisHistory, getDiagnosisIcon, getDiagnosisColor, handleLogout, downloadAnalysisPDF, clearHistory, historyLoading]);

  // Main render logic
  // While checking auth on refresh, show a lightweight loader
  if (isAuthLoading) {
    return <LoadingScreen />;
  }

  if (!user && currentView !== 'home' && currentView !== 'auth' && currentView !== 'reset-password') {
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
          onToggleMode={toggleAuthMode}
          onBackToHome={() => setCurrentView('home')}
          onForgotPassword={() => setCurrentView('reset-password')}
        />
      );
    case 'start':
      return <StartPage />;
    case 'dashboard':
      return <DashboardPage />;
    case 'results':
      return <ResultsPage />;
    case 'reset-password':
      return (
        <ResetPasswordView
          resetEmail={resetEmail}
          setResetEmail={setResetEmail}
          onBackToAuth={() => setCurrentView('auth')}
        />
      );
    case 'history':
      return <HistoryPage />;
    case 'profile':
      return <ProfilePage />;
    case 'change-password':
      return <ChangePasswordPage />;
    default:
      return <HomePage />;
  }
};

export default VisionCareApp;