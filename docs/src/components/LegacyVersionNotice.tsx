import React from 'react';
import Admonition from '@theme/Admonition';

// DATAGO-139020: the 1.x docs have moved to docs.solace.com. This banner is
// rendered at the top of every doc page (via the DocItem/Content swizzle) so
// the whole legacy site is clearly marked as deprecated.
export default function LegacyVersionNotice(): JSX.Element {
  return (
    <Admonition type="warning" title="The information on this page is for Solace Agent Mesh 1.x">
      <p>
        Visit the{' '}
        <a href="https://docs.solace.com/Agent-Mesh/agent-mesh.htm">
          Solace Documentation site
        </a>{' '}
        for information about <strong>Solace Agent Mesh 2.x</strong> and later.
      </p>
      <a
        className="button button--primary"
        href="https://docs.solace.com/Agent-Mesh/agent-mesh.htm">
        Explore the Agent Mesh 2.x docs →
      </a>
    </Admonition>
  );
}
