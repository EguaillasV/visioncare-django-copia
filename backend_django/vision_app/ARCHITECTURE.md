# Arquitectura Hexagonal (Ports & Adapters)

Este módulo `vision_app` aplica un enfoque hexagonal dentro del monolito Django.

- Dominio (`domain/`): lógica pura (métricas OpenCV, ROI, reglas de diagnóstico) sin depender de Django/ONNX/Storage.
- Aplicación (`application/`): casos de uso y puertos (interfaces) que definen límites con el exterior.
- Adaptadores (`adapters/`): implementaciones concretas a frameworks/tecnologías (Django ORM, ONNX, Storage local/Supabase).

Regla de dependencias: las capas externas dependen hacia adentro, nunca al revés.

## Carpetas
- domain/
  - image_processing.py: mejoras de imagen, ROI, métricas y reglas auxiliares.
  - diagnosis.py: reglas y fusión de señales para diagnóstico/severidad/confianza.
- application/
  - ports/
    - repositories.py: AnalysisRepo (crear análisis), UserRepo (ejemplo).
    - ai_services.py: EyeDiseaseDetector (inferencias IA).
    - storage.py: FileStorage (guardar preview procesado).
  - use_cases/
    - upload_and_analyze_image.py: orquestación del flujo de análisis (abre imagen, procesa, IA, persiste y devuelve extras).
- adapters/
  - ai/onnx_detector.py: usa `infer.py` (onnxruntime) para implementar EyeDiseaseDetector.
  - repositories/orm_repositories.py: mapea AnalysisRepo a Django ORM.
  - storage/file_storage.py: guarda previews en MEDIA y retorna URL absoluta.
  - storage/supabase_storage.py: guarda previews en Supabase y retorna URL pública/firmada.
  - storage/supabase_django_storage.py: backend de Django Storage para originales (bucket de Supabase), con caché ligera de URLs firmadas.

## Wiring / Configuración
- `config/container.py` construye los casos de uso inyectando adapters según flags de entorno.
  - `VC_STORAGE` ∈ {`media`, `supabase`}: selecciona `MediaFileStorage` o `SupabaseFileStorage` para previews.
  - Otros flags relevantes: `VC_SIGNED_URL_EXPIRES`, `VC_PREVIEWS_BUCKET`, y proveedores de ONNX si el adapter los soporta.

## Import rules (rutas correctas)
- Usa SIEMPRE imports organizados:
  - `vision_app.adapters.storage.*`
  - `vision_app.adapters.ai.*`
  - `vision_app.adapters.repositories.*`
  - `vision_app.application.ports.*`
  - `vision_app.application.use_cases.*`
- Eliminados los archivos legacy en la raíz de `adapters/` y la carpeta `vision_app/ports/`. No existen shims; no usar rutas antiguas.

## Endpoint
Las vistas (DRF) actúan como adaptadores primarios HTTP. Delegan en los casos de uso (p. ej. `UploadAndAnalyzeImage`).

## Testing sugerido
- Unit tests del caso de uso con dobles para los puertos (sin DB ni ONNX).
- Tests de integración para adaptadores (ORM, ONNX, Storage).

## Beneficios
- Testabilidad, menor acoplamiento, reemplazo de tecnología (p. ej. ONNX local → servicio externo) sin tocar la lógica de aplicación.