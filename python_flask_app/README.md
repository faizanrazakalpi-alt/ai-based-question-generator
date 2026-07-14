# AI Based Question Generator (Python Flask + Jinja2 + MySQL + OpenAI)

This directory contains the standalone Python Flask application for local execution as requested, featuring:
1. **Flask + Jinja2 Templates**: Render parameters, generated questions, historical lists, and profile panels with Tailwind CSS.
2. **MySQL Persistence**: Store question sets, single questions, options arrays, and educator profile stats.
3. **OpenAI API Integration**: Model structured question generation using latest Chat Completions patterns.

---

## 🛠️ Local Development Setup

To run this Python Flask application locally, follow these steps:

### 1. Prerequisites
- Python 3.8 or higher installed on your system.
- MySQL Server (Local instance, Docker, or Cloud Instance) running and accessible.

### 2. Prepare Environment Variables
Create a `.env` file in the `python_flask_app` folder with your custom values:

```env
# Flask Settings
FLASK_SECRET_KEY="your_secret_session_key"

# OpenAI API Settings
OPENAI_API_KEY="your_openai_api_key"

# MySQL Database Settings
DB_HOST="localhost"
DB_PORT=3306
DB_USER="root"
DB_PASSWORD="your_mysql_password"
DB_NAME="ai_question_generator"
```

### 3. Initialize MySQL Database Structure
Run the provided SQL initialization schema against your MySQL Server:
```bash
mysql -u root -p < schema.sql
```
*(Alternatively, you can copy-paste the SQL contents from `schema.sql` into MySQL Workbench, phpMyAdmin, or any SQL console).*

### 4. Install Dependencies
Run the following command inside this directory to install the necessary python packages:
```bash
pip install -r requirements.txt
```

### 5. Launch the Server
Boot up the Flask web application:
```bash
python app.py
```

The application will launch on **`http://localhost:5000`**! Open it in your web browser to start generating and tracking questions.
