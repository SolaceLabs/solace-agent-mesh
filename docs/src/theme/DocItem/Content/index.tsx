import React from 'react';
import Content from '@theme-original/DocItem/Content';
import type ContentType from '@theme/DocItem/Content';
import type {WrapperProps} from '@docusaurus/types';
import LegacyVersionNotice from '@site/src/components/LegacyVersionNotice';

type Props = WrapperProps<typeof ContentType>;

// DATAGO-139020: the 1.x docs have moved to docs.solace.com. Render the legacy
// version notice at the top of every doc page's content so the whole site is
// clearly marked as deprecated (see also noIndex in docusaurus.config.ts).
export default function ContentWrapper(props: Props): JSX.Element {
  return (
    <>
      <LegacyVersionNotice />
      <Content {...props} />
    </>
  );
}
