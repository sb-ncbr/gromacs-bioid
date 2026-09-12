import React from 'react';
import { CombinatorRendererProps, OwnPropsOfControl, RankedTester } from '@jsonforms/core';
export interface OwnOneOfProps extends OwnPropsOfControl {
    indexOfFittingSchema?: number;
}
export declare const MaterialOneOfRenderer: ({ handleChange, schema, path, renderers, cells, rootSchema, id, visible, indexOfFittingSchema, uischema, uischemas, data, }: CombinatorRendererProps) => React.JSX.Element;
export declare const materialOneOfControlTester: RankedTester;
declare const _default: React.ComponentType<OwnPropsOfControl>;
export default _default;
