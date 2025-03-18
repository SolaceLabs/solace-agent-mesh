# Solace Agent Builder (SAM) - Development Guide

## Commands
- **Frontend**: `cd frontend && npm start` - Start the React frontend
- **Backend**: `cd backend && flask run --debug` - Start Flask backend in debug mode
- **Lint**: `cd frontend && npm run lint` or `cd backend && flake8`
- **Format**: `cd frontend && npm run format` or `cd backend && black .`
- **Test**: `cd frontend && npm test` or `cd backend && pytest`
- **Single Test**: `cd backend && pytest tests/test_file.py::test_function`

## Code Style
- **Imports**: Group standard library, third-party, and local imports
- **Formatting**: Use Prettier for frontend, Black for backend
- **Types**: Use TypeScript for frontend, type hints for Python backend
- **Naming**: camelCase for JS/TS, snake_case for Python
- **Colors**: Use theme constants: solace-blue (#0c2139), solace-green (#00af83)
- **Error Handling**: Try/catch in frontend, proper exception handling in backend
- **API**: RESTful endpoints with clear request/response documentation
- **UI**: Modern, sleek interface with focus on natural language interaction