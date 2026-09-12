import React from 'react';
import { ControlProps } from '@jsonforms/core';
export interface WithInput {
    input: any;
}
export declare const MaterialInputControl: (props: ControlProps & WithInput) => React.JSX.Element;
