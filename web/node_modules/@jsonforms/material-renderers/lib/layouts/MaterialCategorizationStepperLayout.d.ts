import React from 'react';
import { RankedTester, StatePropsOfLayout } from '@jsonforms/core';
import { TranslateProps } from '@jsonforms/react';
import { AjvProps } from '../util/layout';
export declare const materialCategorizationStepperTester: RankedTester;
export interface CategorizationStepperState {
    activeCategory: number;
}
export interface MaterialCategorizationStepperLayoutRendererProps extends StatePropsOfLayout, AjvProps, TranslateProps {
    data: any;
}
export declare const MaterialCategorizationStepperLayoutRenderer: (props: MaterialCategorizationStepperLayoutRendererProps) => React.JSX.Element;
declare const _default: (props: MaterialCategorizationStepperLayoutRendererProps & import("@jsonforms/core").OwnPropsOfLayout) => React.JSX.Element;
export default _default;
