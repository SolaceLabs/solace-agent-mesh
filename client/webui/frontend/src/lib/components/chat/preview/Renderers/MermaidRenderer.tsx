import React, { useEffect, useMemo, useState } from "react";

import DOMPurify from "dompurify";

import type { BaseRendererProps } from ".";

export const MermaidRenderer: React.FC<BaseRendererProps> = ({ content, setRenderError }) => {
    const [srcDoc, setSrcDoc] = useState("");

    // Sanitize the Mermaid markdown content before embedding
    const sanitizedContent = useMemo(() => {
        return DOMPurify.sanitize(content, {
            USE_PROFILES: { html: false },
            ALLOWED_TAGS: ["br", "em", "strong", "b", "i"],
            ALLOWED_ATTR: [],
        });
    }, [content]);

    useEffect(() => {
        // Construct the srcDoc
        setSrcDoc(`<!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mermaid Preview</title>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/panzoom@9.4.0/dist/panzoom.min.js"></script>
        <script>
          document.addEventListener('DOMContentLoaded', function() {
            try {
              mermaid.initialize({
                startOnLoad: true,
                theme: 'default',
                fontFamily: 'arial, sans-serif',
                logLevel: 'error',
                securityLevel: 'strict'
              });

              // Initialize panzoom after Mermaid rendering 
              mermaid.run().then(() => {
                const diagramContainer = document.getElementById('diagram-container');
                if (diagramContainer) {
                  const pz = panzoom(diagramContainer, {
                    maxZoom: 10,
                    minZoom: 0.1,
                    smoothScroll: true,
                    bounds: true,
                    boundsPadding: 0.1
                  });
                  // Add zoom controls (old version had only reset)
                  const resetButton = document.getElementById('reset');
                  if (resetButton) {
                    resetButton.addEventListener('click', () => {
                      pz.moveTo(0, 0);
                      pz.zoomAbs(0, 0, 1);
                    });
                  }
                }
              }).catch(err => {
                  console.error("Mermaid rendering failed inside iframe:", err);
                  const mermaidDiv = document.querySelector('.mermaid');
                  if (mermaidDiv) mermaidDiv.innerText = "Error rendering diagram: " + err.message;
              });

              window.addEventListener('message', function(event) {
                if (event.data && event.data.action === 'getMermaidSvg') {
                  const svgElement = document.querySelector('.mermaid svg');
                  if (svgElement) {
                    if (!svgElement.getAttribute('xmlns')) { // Ensure xmlns for standalone SVG
                        svgElement.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
                    }
                    const svgData = new XMLSerializer().serializeToString(svgElement);
                    window.parent.postMessage({
                      action: 'downloadSvg',
                      svgData: svgData,
                      filename: event.data.filename || 'mermaid-diagram.svg'
                    }, '*');
                  } else {
                    console.error('SVG element not found for download inside iframe.');
                  }
                }
              });
            } catch (e) {
              console.error("Error initializing Mermaid or Panzoom inside iframe:", e);
              const mermaidDiv = document.querySelector('.mermaid');
              if (mermaidDiv) mermaidDiv.innerText = "Failed to initialize diagram viewer: " + e.message;
            }
          });
        </script>
        <style>
          /* Styles from old code */
          html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            overflow: hidden;
            font-family: Arial, sans-serif; /* Old font */
          }
          .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
          }
          .diagram-wrapper {
            flex: 1;
            overflow: hidden;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #f9f9f9;
          }
          #diagram-container {
            transform-origin: 0 0;
            cursor: grab;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            /* Ensure diagram container can hold the content */
            width: auto; /* Adjust as needed, or let content define it */
            height: auto;
            max-width: 100%;
            max-height: 100%;
          }
          #diagram-container:active {
            cursor: grabbing;
          }
          .mermaid {
            display: flex; /* Helps in centering if SVG is smaller */
            justify-content: center;
            align-items: center;
            /* width: 100%; Ensures mermaid div takes space, SVG might scale within it */
            /* height: 100%; */
          }
          .mermaid svg {
             max-width: 100%; /* Ensure SVG scales down if too large */
             max-height: 100%;
          }
          .controls{
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            display: flex;
            gap: 5px;
          }
          .control-btn {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background-color: white;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            cursor: pointer;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .control-btn:hover {
            background-color: #f0f0f0;
          }
          .instructions {
            position: fixed;
            top: 10px;
            left: 10px;
            background-color: rgba(255,255,255,0.8);
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            color: #666;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="diagram-wrapper">
            <div id="diagram-container">
              <div class="mermaid">
                ${sanitizedContent}
              </div>
            </div>
          </div>
          <div class="instructions">
            Drag to pan and scroll to zoom
          </div>
          <div class="controls">
            <button id="reset" class="control-btn" title="Reset View">↺</button>
          </div>
        </div>
      </body>
      </html>`);
    }, [sanitizedContent]);

    return (
        <div className="bg-background h-full p-4">
            <iframe
                srcDoc={srcDoc}
                title="Mermaid Diagram Preview"
                sandbox="allow-scripts allow-same-origin allow-downloads"
                className="h-96 w-full resize border-none"
                onError={() => setRenderError("Failed to load Mermaid content.")}
                onLoad={() => setRenderError(null)}
            />
        </div>
    );
};
