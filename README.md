# Tōdai - Study Dashboard

A comprehensive study dashboard with AI-powered features.

## Features
- AI Flashcards
- Practice Questions
- Focus Timer
- Todo List
- Calendar
- Quotes

## Deployment to Render

### 1. Push to GitHub
```bash
cd Todai
git init
git add .
git commit -m "Initial commit"
# Create a new repository on GitHub and push
```

### 2. Deploy on Render
1. Go to https://dashboard.render.com
2. Create a new **Web Service**
3. Connect your GitHub repository
4. Configure:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Environment Variables: Add `GROQ_API_KEY` and `FLASK_SECRET_KEY`

### 3. Environment Variables Needed
- `GROQ_API_KEY` - Get from https://console.groq.com
- `FLASK_SECRET_KEY` - Generate a secure random key

## Local Development
```bash
cd Todai
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000
