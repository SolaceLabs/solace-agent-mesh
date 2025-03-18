#!/bin/bash

echo "Setting up Solace Agent Builder..."

# Setup backend
echo "Setting up backend..."
cd backend
python -m pip install -r requirements.txt
cd ..

# Setup frontend
echo "Setting up frontend..."
cd frontend
npm install
cd ..

echo "Setup complete! You can now run the following commands:"
echo "- Backend: cd backend && flask run --debug"
echo "- Frontend: cd frontend && npm start"