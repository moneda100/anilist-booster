# anilist-booster
**AniList Booster** es una aplicación de escritorio desarrollada en Python para gestionar y seguir tus listas de anime y manga de forma eficiente, utilizando la API de AniList.
![image alt](https://github.com/moneda100/anilist-booster/blob/ddfa54bed1a5ce360855d2d18e4f7f1c08c7b7ba/ejemplo%20visual.png) 
## 🚀 Características

- 📋 **Gestión de Listas:** Visualiza y actualiza tu progreso (episodios, capítulos, puntuación y estado) de tus listas personales.
- 🔍 **Búsqueda Avanzada:** Encuentra cualquier anime o manga en la base de datos global.
- 🔥 **Tendencias:** Explora lo más popular del momento directamente en la app.
- 👤 **Perfil y Estadísticas:** Revisa tus estadísticas de tiempo visto, capítulos leídos y tus favoritos.
- 🎲 **Descubrimiento Aleatorio:** Encuentra nuevas recomendaciones con la función de selección al azar.
- 🎨 **Interfaz Moderna:** Basada en `ttkbootstrap` con temas oscuros para una mejor experiencia visual.

## 🛠️ Instalación

1. **Requisitos previos:**
   - Tener instalado Python 3.x.
   - Una cuenta en AniList.

2. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/anilist-booster.git
   cd anilist-booster
   ```

3. **Instalar las dependencias:**
   Ejecuta el siguiente comando para instalar las librerías necesarias:
   ```bash
   pip install ttkbootstrap requests Pillow
   ```

4. **Ejecutar la aplicación:**
   ```bash
   python main.py
   ```

## 🔑 Guía de Configuración y Login

Para que la aplicación pueda conectarse a tu cuenta y guardar tu progreso, debes registrar una aplicación en AniList:

### 1. Obtener tu Client ID
1. Inicia sesión en AniList.co.
2. Ve a Settings > Developer.
3. Haz clic en **"Create New App"**.
4. En el campo **Name**, pon `AniList Booster`.
5. En **Redirect URL**, escribe exactamente: `https://anilist.co/api/v2/oauth/pin`
6. Guarda los cambios y copia el número de **Client ID** que te proporcionen.

### 2. Iniciar sesión en la App
1. Abre la aplicación y haz clic en el botón **"Iniciar sesión"** (arriba a la derecha).
2. Pega tu **Client ID** en el primer cuadro de texto.
3. Haz clic en **"Abrir autorización en el navegador"**.
4. Se abrirá una web donde AniList te pedirá permiso; haz clic en **"Autorizar"**.
5. Verás un código (Token). Cópialo.
6. Regresa a la app, pega ese código en el campo **"Token de acceso"** y haz clic en **"Iniciar sesión"**.

---
*Nota: La aplicación guardará tu token localmente en `anilist_token.json` para que no tengas que loguearte cada vez que la abras.*

## 📄 Licencia
Este proyecto está bajo la licencia MIT.
