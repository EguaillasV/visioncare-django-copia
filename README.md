# VisionCare Web Application

AI-Powered Eye Disease Detection System built with Django REST Framework and React.

## Architecture

- Backend: Django 5 + DRF + JWT, organizado con arquitectura Hexagonal (Ports & Adapters)
- Frontend: React + Tailwind CSS
- Base de datos: PostgreSQL/Supabase (obligatorio)
- IA: OpenCV (reglas) + ONNX Runtime opcional (clasificador)

## Estructura del proyecto

```
VISIONCARE_WEB/
├── backend_django/              # Backend Django
│   ├── manage.py
│   ├── requirements.txt
│   ├── tools/                   # Utilidades (limpieza, conversión ONNX, etc.)
│   ├── visioncare_django/       # Proyecto (settings, urls, wsgi)
│   └── vision_app/              # App principal (Hexagonal)
│       ├── domain/              # Lógica pura (OpenCV, reglas)
│       ├── application/         # Casos de uso y puertos
│       │   ├── ports/
│       │   └── use_cases/
│       ├── adapters/            # Integraciones (ORM, ONNX, storage)
│       ├── config/              # Wiring/DI ligero (container)
│       ├── onnx_models/         # Modelos ONNX (+ .json)
│       ├── ARCHITECTURE.md      # Documentación de la arquitectura
│       └── (models, views, serializers, urls)
├── frontend/                    # React (proyecto de Node aislado)
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── tailwind.config.js
├── .gitignore                   # Ignora venv, media, logs, builds
└── README.md
```

## Inicio rápido

### Backend (Windows CMD)
```bat
cd backend_django
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

### Frontend
```bat
cd frontend
npm install
npm start
```

## Variables de entorno

### Backend (archivo backend_django/.env)
```
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://postgres:password@YOUR-PROJECT.supabase.co:5432/postgres
DB_SSL_REQUIRE=true
# URL base para links absolutos (opcional)
SITE_URL=http://localhost:8001
# ONNX opcional
# VC_ONNX_MODEL=C:\\absolute\\path\\to\\classifier.onnx
# VC_ONNX_MODELS=C:\\path\\model1.onnx;C:\\path\\model2.onnx
# Umbrales de fusión
# VC_P_CATARACT_HIGH=0.75
# VC_P_CATARACT_MID=0.55
```

### Frontend (archivo frontend/.env)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Endpoints API (principales)

- POST /api/auth/register/
- POST /api/auth/login/
- GET  /api/auth/profile/
- POST /api/analyze-image/
- GET  /api/history/
- GET  /api/download-analysis/{id}/

## Housekeeping

- No comprometas `backend_django/venv/` ni `backend_django/media/`.
- Usa `backend_django/tools/cleanup_workspace.py` para limpiar caches y logs.
- Modelos ONNX: versiona solo `.onnx` y `.json` (metadatos), no checkpoints `.pt/.pth`.

## Licencia

MIT License