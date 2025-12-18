# Agent Rules Standard

This document defines the rules and guidelines for AI-assisted development in the Solace Agent Mesh project. It serves as the primary reference for AI agents working on this codebase.

---

## 1. Project Overview

### 1.1 Technology Stack
- **Languages:** Python 3.10+, TypeScript/React
- **Testing:** pytest, asyncio
- **Backend:** FastAPI, Solace PubSub+, Google ADK
- **Architecture:** Event-driven agent mesh with A2A protocol messaging

### 1.2 Knowledge Sources (Context7 MCP)
- `solacelabs/solace-agent-mesh` library – Solace Agent Mesh codebase
- `google/adk-python` library – Google ADK Python library
- `https://google.github.io/adk-docs`library – Google ADK documentation
- `solacelabs/solace-ai-connector` library – Solace AI Connector

### 1.3 Project Structure
```
src/solace_agent_mesh/     # Core framework (READ for tracing bugs)
├── agent/                 # Agent components, proxies, SAC, protocol handlers
├── common/                # Shared utilities, services, middleware, A2A artifacts
├── gateway/               # Gateway implementations (HTTP/SSE, generic, base)
└── core_a2a/              # Core A2A service implementation

cli/                       # Command-line interface and utilities
client/webui/frontend/     # React frontend application

tests/                     # All test suites (WRITE tests here)
├── unit/                  # Unit tests for isolated components
├── integration/           # Integration tests for component interactions
├── system/                # End-to-end system tests
└── [agent|common|gateway]/ # Component-specific test directories

pyproject.toml             # Project dependencies and hatch configuration
```

---

## 2. Development Commands

### 2.1 Environment Setup
```bash
hatch env create    # Setup development environment
hatch shell         # Activate development shell
```

### 2.2 Code Generation
```bash
sam add agent --gui       # Interactive agent creation
sam add gateway --gui     # Interactive gateway creation
sam plugin create <name>  # Create custom plugin structure
```

### 2.3 Testing Commands
```bash
# Run tests
hatch run test                                      # All tests
hatch run test:unit                                 # Unit tests only
hatch run test:integration                          # Integration tests only
hatch run test:cov                                  # With coverage report
hatch run pytest tests/unit/cli/test_main.py -v    # Specific module

# Frontend tests
cd client/webui/frontend && npm test               # React tests
cd client/webui/frontend && npm run lint           # Frontend linting
```

### 2.4 Code Quality
```bash
hatch run format       # Format code with Black
hatch run lint         # Run linting checks
hatch run type-check   # Run mypy type checking
```

---

## 3. Development Methodology

### 3.1 Development Workflow
1. **Requirements Analysis** – Understand PRD specifications and technical requirements
2. **Design Planning** – Plan component architecture and integration points
3. **Vertical Slice Implementation** – Build end-to-end functionality in small increments
4. **Code Creation/Refactoring** – Write clean, maintainable code following project patterns
5. **Configuration Setup** – Create appropriate YAML configs and templates
6. **Testing Integration** – Ensure new code has corresponding test coverage
7. **Documentation** – Document new features and configuration options

### 3.2 Vertical Slice Approach
Build features incrementally using vertical slices:

1. **Start Small** – Implement minimal viable feature first
2. **End-to-End** – Build complete flow from UI to backend
3. **Iterate** – Add complexity and features incrementally
4. **Test Early** – Add tests for each slice
5. **Integrate Continuously** – Ensure each slice works with existing system

### 3.3 Debugging Process
1. **Bug Identification** – Analyze error logs, stack traces, and symptoms
2. **Code Tracing** – Follow execution paths systematically using file reads
3. **Root Cause Analysis** – Identify fundamental issue with code references
4. **Impact Assessment** – Determine scope and severity across codebase
5. **Solution Design** – Recommend targeted fixes with minimal side effects
6. **Test Creation** – Write comprehensive tests to verify fixes and prevent regressions
7. **Execution & Analysis** – Run tests (with approval) and analyze results

---

## 4. Coding Standards

### 4.1 Python Backend (PEP8 + Google Style Guide)
- Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- Use type hints for all function parameters and returns
- Follow existing project patterns for error handling

### 4.2 TypeScript/React Frontend
- Use TypeScript strict mode
- Follow React functional components with hooks
- Use Tailwind CSS for styling
- Implement proper error boundaries

### 4.3 Configuration Management
- Follow existing template patterns in `templates/`
- Include proper validation and defaults
- Document configuration options clearly in `docs/` folder

---

## 5. Testing Guidelines

### 5.1 Testing Principles
- Write clear, maintainable tests following existing patterns in `tests/`
- Use appropriate mocking for external dependencies (LLM services, message brokers)
- Test both success and failure scenarios with meaningful assertions
- Write tests so developers new to the codebase can understand expected behavior
- Run tests after writing them to verify they pass
- Analyze test results and fix issues before marking work complete

---

## 6. Operational Boundaries

### 6.2 Ask First ⚠️
- Before running tests or executing any commands