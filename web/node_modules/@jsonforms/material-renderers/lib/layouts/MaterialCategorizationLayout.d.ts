import React from 'react';
import { RankedTester, StatePropsOfLayout, Tester } from '@jsonforms/core';
import { TranslateProps } from '@jsonforms/react';
import { AjvProps } from '../util/layout';
export declare const isSingleLevelCategorization: Tester;
export declare const materialCategorizationTester: RankedTester;
export interface CategorizationState {
    activeCategory: number;
}
export interface MaterialCategorizationLayoutRendererProps extends StatePropsOfLayout, AjvProps, TranslateProps {
    selected?: number;
    ownState?: boolean;
    data?: any;
    onChange?(selected: number, prevSelected: number): void;
}
export declare const MaterialCategorizationLayoutRenderer: (props: MaterialCategorizationLayoutRendererProps) => React.JSX.Element;
declare const _default: (props: MaterialCategorizationLayoutRendererProps & import("@jsonforms/core").OwnPropsOfLayout) => React.JSX.Element;
export default _default;
