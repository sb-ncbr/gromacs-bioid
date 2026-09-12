import { ControlProps, DispatchPropsOfMultiEnumControl, OwnPropsOfEnum, RankedTester } from '@jsonforms/core';
import React from 'react';
export declare const MaterialEnumArrayRenderer: ({ config, id, schema, visible, errors, description, label, required, path, options, data, addItem, removeItem, handleChange: _handleChange, ...otherProps }: ControlProps & OwnPropsOfEnum & DispatchPropsOfMultiEnumControl) => React.JSX.Element;
export declare const materialEnumArrayRendererTester: RankedTester;
declare const _default: React.ComponentType<import("@jsonforms/core").OwnPropsOfControl & OwnPropsOfEnum & DispatchPropsOfMultiEnumControl>;
export default _default;
