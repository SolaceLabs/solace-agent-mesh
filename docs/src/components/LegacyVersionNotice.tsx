import React from 'react';
import Admonition from '@theme/Admonition';

// DATAGO-139020: the 1.x docs have moved to docs.solace.com. This banner is
// rendered at the top of every doc page (via the DocItem/Content swizzle) so
// the whole legacy site is clearly marked as deprecated.
export default function LegacyVersionNotice(): JSX.Element {
  return (
    <Admonition type="warning" title="This documentation is for Solace Agent Mesh 1.x">
      <p>
        You are viewing the documentation for <strong>Solace Agent Mesh 1.x</strong>. The
        latest documentation for <strong>Solace Agent Mesh 2.x</strong> and later is now
        hosted on docs.solace.com.
      </p>
      <a
        className="button button--primary"
        href="https://docs.solace.com/Agent-Mesh/agent-mesh.htm">
        Go to the Solace Agent Mesh 2.x documentation →
      </a>
    </Admonition>
  );
}
