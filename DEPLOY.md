# Deployment & Ngrok Guide

## 1. Deploying to Render
Your project is configured for Render.

1.  **Push your code to GitHub/GitLab**.
2.  **Create a New Web Service on Render**:
    -   Connect your repository.
    -   **Build Command**: `./build.sh`
    -   **Start Command**: `gunicorn manacine_project.wsgi:application`
    -   **Environment Variables**:
        -   `PYTHON_VERSION`: `3.9` (or your version)
        -   `SECRET_KEY`: (Generate a strong key)
        -   `DEBUG`: `False`
        -   `CLOUDINARY_URL`: (Your Cloudinary URL)
        -   `DATABASE_URL`: (Your Neon/Postgres URL)

## 2. Using Ngrok (Local Tunnel)
To expose your local server to the internet for testing:

1.  **Install Ngrok** (if not already installed).
2.  **Start your Django Server**:
    ```bash
    python manage.py runserver
    ```
3.  **Start Ngrok** (in a new terminal):
    ```bash
    ngrok http 8000
    ```
4.  Copy the URL (e.g., `https://random-name.ngrok-free.app`) and use it. We have already configured `ALLOWED_HOSTS` to accept it.
