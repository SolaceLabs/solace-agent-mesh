# Overview
Create a specialized data analysis agent within the Solace Agent Mesh framework that processes structured data files and generates insights. The agent will load data from various formats (CSV, Excel, JSON), perform statistical analysis, create visualizations, and transform datasets based on natural language instructions. The focus is on a functional, reusable agent built incrementally using a vertical slice approach suitable for LLM-assisted development.

# Core Features
- Data Loading & Inspection: Load and inspect structured data from CSV, Excel, JSON, and Parquet files with automatic schema detection and data quality reporting.
- Statistical Analysis: Perform descriptive statistics (mean, median, std, quartiles), correlation analysis, and distribution analysis on numeric columns.
- Data Transformation: Clean, filter, sort, aggregate, and pivot datasets based on natural language instructions using pandas operations.
- Visualization Generation: Create charts (line, bar, scatter, histogram, heatmap) and save them as PNG artifacts for easy sharing and reference.
- Natural Language Querying: Execute natural language queries to filter and extract specific data subsets without requiring SQL or pandas syntax knowledge.

# Implementation Guidelines
- Framework & Architecture: Utilize the Solace Agent Mesh framework with YAML-based configuration following patterns from existing agents.
- Tool Integration: Implement Python-based builtin tools leveraging pandas, numpy, and matplotlib/seaborn libraries for data operations and visualization.
- Configuration Pattern: Follow the established YAML structure with shared_config.yaml inclusion, broker connection configuration, and agent card publishing.
- Development Approach: Employ a vertical slice implementation strategy. Start with basic CSV loading and simple statistics, then incrementally add visualization, transformation, and advanced analysis capabilities. This approach is suitable for LLM-assisted coding.
- Scope: Focus on core data analysis functionality for datasets up to 100K rows; avoid over-engineering for big data processing or machine learning model training initially.