# Solace Agent Builder (SAM)

A modern web application for creating intelligent agents within the Solace Agent Mesh framework.

## Project Structure

- `/frontend` - React TypeScript frontend application
- `/backend` - Flask Python backend application

## Getting Started

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Start the Flask server:
   ```
   python run.py
   ```
   
   Or alternatively:
   ```
   flask run --debug --host=0.0.0.0
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

## Features

- Create agents using natural language descriptions
- Modern, sleek UI with Solace branding
- Optional API key integration
- Simple agent creation workflow

## Development

- Backend API runs on `http://localhost:5002`
- Frontend development server runs on `http://localhost:3000`

## Technology Stack

- **Frontend**: React, TypeScript, CSS3
- **Backend**: Flask, Python