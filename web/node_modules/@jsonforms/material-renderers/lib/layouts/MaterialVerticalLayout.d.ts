import React from 'react';
import { LayoutProps, RankedTester } from '@jsonforms/core';
/**
 * Default tester for a vertical layout.
 * @type {RankedTester}
 */
export declare const materialVerticalLayoutTester: RankedTester;
export declare const MaterialVerticalLayoutRenderer: ({ uischema, schema, path, enabled, visible, renderers, cells, }: LayoutProps) => React.JSX.Element;
declare const _default: React.ComponentType<LayoutProps & import("@jsonforms/core").OwnPropsOfLayout>;
export default _default;
