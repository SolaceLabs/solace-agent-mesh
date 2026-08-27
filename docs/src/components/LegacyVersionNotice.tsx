import React from 'react';
import Admonition from '@theme/Admonition';

// GENERATED from messages/solace-agent-mesh.md by deprecate.py (DATAGO-147013).
// Edit the message and re-run `restage`; do not hand-edit this file. Rendered at
// the top of every doc page via the DocItem/Content swizzle; site-wide noindex
// stays set in docusaurus.config.ts.

export default function LegacyVersionNotice(): JSX.Element {
  return (
    <Admonition type="danger" title="Solace Agent Mesh in Python is now deprecated">
      <p>👋 Thank you to everyone who has built with Solace Agent Mesh! This Python version is now <strong>deprecated</strong> — it&apos;s no longer under active development and won&apos;t receive new features, bug fixes or security updates.</p>
      <p>🚀 <strong>Check out the new version of Solace Agent Mesh</strong> → <a href="https://docs.solace.com/Agent-Mesh/agent-mesh.htm">https://docs.solace.com/Agent-Mesh/agent-mesh.htm</a></p>
      <p>🖥️ A free edition of the Solace Agent Mesh desktop app is available: <a href="https://solace.com/products/agent-mesh/download/">https://solace.com/products/agent-mesh/download/</a></p>
      <p>This repository will be archived (read-only) but stays available for reference, so your existing links and installs keep working.</p>
    </Admonition>
  );
}
