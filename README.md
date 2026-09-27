# 🏡 Radar Inmobiliario - Mendoza

Agente automatizado inteligente para detectar oportunidades inmobiliarias en **Mendoza (Capital), Godoy Cruz, Guaymallén y Las Heras**.

## 🎯 Criterios Configurados

- **Categoría A (Excluyentes):**
  - **Ubicación:** Mendoza (Capital), Godoy Cruz, Guaymallén, Las Heras.
  - **Tipo de Inmueble:** Departamento o Casa únicamente.
  - **Presupuesto disponible:** USD 120.000 (Tope estricto de búsqueda con margen: USD 132.000).
- **Categoría B (Deseados con tolerancia):**
  - **Superficie:** Desde 50 m² (rango de 40 a 50 m² admitido con menor puntuación).
  - **Margen de Contraoferta:** Propiedades entre USD 120k y USD 132k son analizadas por la IA buscando señales de urgencia, días publicadas o apertura a negociar.
- **Categoría C (Características muy deseables):**
  - Seguridad / Barrio privado (especialmente para casas).
  - Red de gas natural (fundamental para el invierno mendocino).
  - Cochera propia.
  - 2 o más baños.
  - Último piso (en caso de departamentos).

---

## 🚀 Cómo Usarlo

### 1. Ejecución Manual por Consola
Para buscar y generar el informe de hoy:
```bash
.\.venv\Scripts\python.exe main.py
```
Esto generará:
- `data/latest_run.json`: Todas las propiedades analizadas y puntuadas.
- `data/latest_report.html`: Vista previa del correo que puedes abrir en tu navegador (doble clic).

### 2. Panel Visual Interactivo (Streamlit)
Para ver las oportunidades en tarjetas visuales con fotos, filtros por score y botones directos a la publicación:
```bash
.\.venv\Scripts\streamlit.exe run app.py
```

---

## 🔑 Configuración de IA y Correos (Opcional)

Crea o edita el archivo `.env` en la raíz del proyecto:

```env
# Clave gratuita de Google Gemini (Obténla en https://aistudio.google.com/)
GEMINI_API_KEY="AIzaSy..."

# Notificaciones por Gmail
SMTP_SENDER_EMAIL="tucorreo@gmail.com"
SMTP_APP_PASSWORD="xxxx xxxx xxxx xxxx"  # Contraseña de aplicación de Google
SMTP_RECIPIENT_EMAIL="tucorreo@gmail.com"
```

> [!NOTE]
> Si no configuras la clave de Gemini, el agente igualmente funciona mediante su **motor heurístico**, analizando las descripciones y calculando el score a costo \$0 y con 0 tokens.

---

## ⏰ Automatización Diaria

### Opción A: Programador de Tareas de Windows (Local)
1. Abre el menú Inicio y escribe **Programador de tareas**.
2. Selecciona **Crear tarea básica...**
3. Nombre: `Radar Inmobiliario Diario`.
4. Desencadenador: **Diariamente** (ej: 09:00 AM).
5. Acción: **Iniciar un programa**.
   - Programa: `c:\Users\I762371\Documents\Personal\Antigravity\Buscador de Propiedades\.venv\Scripts\python.exe`
   - Argumentos: `main.py`
   - Iniciar en: `c:\Users\I762371\Documents\Personal\Antigravity\Buscador de Propiedades`

### Opción B: En la Nube con GitHub Actions (Gratuito y 24/7)
Puedes subir este repositorio a un GitHub privado y agregar un workflow (`.github/workflows/daily.yml`) que ejecute `main.py` todas las mañanas automáticamente sin depender de tener tu computadora prendida.
