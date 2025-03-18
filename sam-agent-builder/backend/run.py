"""
Run script for the Solace Agent Builder backend.
This script ensures the server is properly configured for development.
"""
from app import app

if __name__ == "__main__":
    # Run the app with explicit host and port, and in debug mode
    print("Starting Solace Agent Builder backend server...")
    print("API endpoints available at:")
    print("  - POST /api/create-agent")
    print("  - GET /api/health")
    print("Server running at http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=True)