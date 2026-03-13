# UDK Mezun Tracker - Setup & Deployment Manual

This guide covers local development setup and production deployment to Render using Neon (PostgreSQL).

## Prerequisites
- Python 3.10+
- A Git client
- A Neon.tech account for PostgreSQL
- A Render.com account for web hosting

---

## 1. Local Development Setup

### Step 1: Locate Your Project Folder
1. I have already created the project files for you on your computer.
2. The project is located at: `C:\Users\rozturk\.gemini\antigravity\scratch\udk_mezun_tracker`
3. Open your terminal (PowerShell) and navigate to that folder:
   ```powershell
   cd C:\Users\rozturk\.gemini\antigravity\scratch\udk_mezun_tracker
   ```

### Step 2: Set up Virtual Environment
It is highly recommended to isolate dependencies using `venv`. Since Python is not in your system PATH, use the direct path to your Python 3.11 installation:
```powershell
C:\Users\rozturk\AppData\Local\Programs\Python\Python311\python.exe -m venv venv
```

**Activate it:**
- **Windows (Command Prompt):** `venv\Scripts\activate.bat`
- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **macOS/Linux:** `source venv/bin/activate`

### Step 3: Install Dependencies
Use the `pip` executable directly from your new virtual environment:
```powershell
.\venv\Scripts\pip.exe install -r requirements.txt
```

### Step 4: Environment Variables (`.env`)
Create a file named `.env` in the root of the project (`udk_mezun_tracker/.env`). Add the following values:
*(Note: If `DATABASE_URL` is omitted, the app will fall back to a local SQLite database for quick testing).*

```dotenv
SECRET_KEY=super-secret-local-key-replace-me
DEBUG=True
# DATABASE_URL=postgresql://user:pass@neon-host.neon.tech/dbname?sslmode=require
```

### Step 5: Database Initialization
Run the application to initialize the database schema automatically. The app handles creating tables before the first request. Be sure to use the virtual environment's Python:

```powershell
.\venv\Scripts\python.exe app.py
```
*Alternatively, you can run `flask run`.* The app will be available at `http://localhost:5000`.

---

## 2. Production Deployment (Neon + Render)

### Step 1: Set up the Neon Database
1. Log into [Neon.tech](https://neon.tech/) and create a new project.
2. Under your Project Dashboard, find the **Connection Details**.
3. Copy the **Connection String** (it starts with `postgres://` or `postgresql://`).
4. Ensure it has `?sslmode=require` at the end (Neon includes this by default).

### Step 2: Upload Your Code to GitHub
Render connects directly to a GitHub repository to automatically deploy your app. If you don't have a GitHub account or don't know how to use Git, you can do this entirely through your web browser!

**Option A: Using the GitHub Website (Beginner Friendly)**
1. Go to [GitHub.com](https://github.com/) and create a free account.
2. Once logged in, click the **"+"** icon in the top right corner and select **"New repository"**.
3. Name the repository `udk-mezun-tracker`. You can make it Public or Private. Click **Create repository**.
4. On the next screen, look for the quick setup section and click the link that says **"uploading an existing file"**.
5. Drag and drop all the files AND folders from your local `udk_mezun_tracker` folder directly into the web browser.
6. Once the uploads finish, click the green **"Commit changes"** button at the bottom.

**Option B: Using the Git Command Line (Advanced)**
If you already have Git installed and configured, you can run:
```bash
git init
git add .
git commit -m "Initial commit for UDK Mezun Tracker"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/udk-mezun-tracker.git
git push -u origin main
```

### Step 3: Configure Render Web Service
1. Log into [Render.com](https://render.com/).
2. Click **New** > **Web Service**.
3. Connect your GitHub account and select your repository.
4. **Configuration details:**
   - **Name:** `udk-mezun-tracker`
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. **Environment Variables:**
   Scroll down to Environment Variables and add the following:
   - `DATABASE_URL`: *(paste the Neon connection string here. Make sure it starts with `postgresql://` not `postgres://`)*
   - `SECRET_KEY`: *(Generate a secure random string, e.g., `python -c "import secrets; print(secrets.token_urlsafe())"`)*
   - `DEBUG`: `False` (Important for production safety!)

### Step 4: Deploy
Click **Create Web Service**. Render will install dependencies and start the app using `gunicorn`.
The app will automatically create the PostgreSQL tables on its first run if they don't exist.

---

## Logging In for the First Time
Because we don't have a registration form for security purposes, you will need to create the first admin manually if starting fresh, or the system can auto-create one. 
*(By default, inside `app.py`, the system creates a default admin user `admin` with password `admin` on the first startup. **CHANGE THIS IMMEDIATELY AFTER LOGIN!**)*
