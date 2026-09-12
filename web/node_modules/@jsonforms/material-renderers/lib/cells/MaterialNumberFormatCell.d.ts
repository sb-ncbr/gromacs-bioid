import React from 'react';
import { CellProps, Formatted, RankedTester, WithClassname } from '@jsonforms/core';
export declare const MaterialNumberFormatCell: (props: CellProps & WithClassname & Formatted<number>) => React.JSX.Element;
/**
 * Default tester for text-based/string controls.
 * @type {RankedTester}
 */
export declare const materialNumberFormatCellTester: RankedTester;
declare const _default: React.ComponentType<import("@jsonforms/core").OwnPropsOfCell>;
export default _default;
