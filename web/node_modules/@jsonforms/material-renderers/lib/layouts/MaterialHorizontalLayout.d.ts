import React from 'react';
import { LayoutProps, RankedTester } from '@jsonforms/core';
/**
 * Default tester for a horizontal layout.
 * @type {RankedTester}
 */
export declare const materialHorizontalLayoutTester: RankedTester;
export declare const MaterialHorizontalLayoutRenderer: ({ uischema, renderers, cells, schema, path, enabled, visible, }: LayoutProps) => React.JSX.Element;
declare const _default: React.ComponentType<LayoutProps & import("@jsonforms/core").OwnPropsOfLayout>;
export default _default;
