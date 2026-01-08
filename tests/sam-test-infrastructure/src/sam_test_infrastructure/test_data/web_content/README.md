# Test Data for Web Content Testing

This directory contains static test files used by the `TestStaticFileServer` for integration testing of the `web_request` tool.

## Files

- **sample.json** - JSON data structure for testing `application/json` content type
- **sample.html** - HTML document for testing `text/html` content type
- **sample.txt** - Plain text file for testing `text/plain` content type
- **sample.xml** - XML document for testing `application/xml` content type
- **sample.csv** - CSV data for testing `text/csv` content type
- **large_file.bin** - Binary file for testing large response handling

## Usage

These files are served by `TestStaticFileServer` during integration tests. The server runs on `http://localhost:8089` by default.

The server supports both GET and POST requests:
- GET requests serve static files from this directory
- POST requests return a default 201 Created response (or configured responses for testing)

Example URLs:
- `http://localhost:8089/sample.json` (GET)
- `http://localhost:8089/sample.html` (GET)
- `http://localhost:8089/posts` (POST)

## Adding New Test Files

1. Add the file to this directory
2. The server will automatically serve it with the appropriate content type based on the file extension
3. Update this README to document the new file

## Content Types

The server automatically determines content types based on file extensions:

| Extension | Content Type |
|-----------|--------------|
| .json | application/json |
| .html, .htm | text/html |
| .txt | text/plain |
| .xml | application/xml |
| .csv | text/csv |
| .png | image/png |
| .jpg, .jpeg | image/jpeg |
| .gif | image/gif |
| .pdf | application/pdf |
| .zip | application/zip |
