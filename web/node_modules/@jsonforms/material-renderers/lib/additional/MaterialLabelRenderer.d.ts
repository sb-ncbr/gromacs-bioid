import React from 'react';
import { LabelProps, RankedTester } from '@jsonforms/core';
/**
 * Default tester for a label.
 * @type {RankedTester}
 */
export declare const materialLabelRendererTester: RankedTester;
/**
 * Default renderer for a label.
 */
export declare const MaterialLabelRenderer: ({ text, visible }: LabelProps) => React.JSX.Element;
declare const _default: React.ComponentType<import("@jsonforms/core").OwnPropsOfLabel>;
export default _default;
