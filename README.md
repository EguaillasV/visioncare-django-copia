# VisionCare Web Application

AI-Powered Eye Disease Detection System built with Django REST Framework and React.

## Architecture

- **Backend**: Django 5.2.6 + Django REST Framework + JWT Authentication
- **Frontend**: React with Tailwind CSS
- **Database**: SQLite (development) / PostgreSQL (production)
- **AI Integration**: OpenAI GPT-4o-mini + OpenCV for image processing
- **Features**: Eye disease detection, analysis history, PDF reports

## Project Structure

```
/
├── backend_django/          # Django backend application
│   ├── manage.py
│   ├── requirements.txt
│   ├── vision_app/         # Main Django app
│   └── visioncare_django/  # Django project settings
├── frontend/               # React frontend application
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── tailwind.config.js
└── README.md
```

## Quick Start

### Backend Setup
```bash
cd backend_django
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

## Environment Variables

### Backend (.env in backend_django/)
```
SECRET_KEY=your-secret-key
DEBUG=True
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=sqlite:///db.sqlite3
```

### Frontend (.env in frontend/)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Key Features

- 🔐 **JWT Authentication**: Secure user registration and login
- 📷 **Image Upload & Webcam**: Multiple ways to capture eye images  
- 🤖 **AI Analysis**: OpenCV + OpenAI for disease detection
- 📊 **Analysis History**: Track user's eye health over time
- 📄 **PDF Reports**: Download detailed analysis reports
- 🎨 **Modern UI**: Responsive design with Tailwind CSS

## API Endpoints

- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `GET /api/auth/profile/` - Get user profile
- `POST /api/analyze-image/` - Analyze eye image
- `GET /api/history/` - Get analysis history
- `GET /api/download-analysis/{id}/` - Download PDF report

## Deployment

This application is ready for deployment on:
- Emergent (recommended)
- Heroku
- Railway
- Any Django-compatible hosting

## Development

Built with modern best practices:
- Django REST Framework for robust APIs
- React Hooks and Context for state management
- OpenCV for advanced image processing
- JWT for secure authentication
- Tailwind CSS for responsive design

## License

MIT License