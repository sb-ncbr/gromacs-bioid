import { ArrayControlProps, ArrayLayoutProps, CellProps, CombinatorRendererProps, ControlProps, DispatchCellProps, DispatchPropsOfControl, EnumCellProps, JsonFormsProps, JsonFormsSubStates, LayoutProps, OwnPropsOfCell, OwnPropsOfControl, OwnPropsOfEnum, OwnPropsOfEnumCell, OwnPropsOfJsonFormsRenderer, OwnPropsOfLayout, OwnPropsOfMasterListItem, StatePropsOfControlWithDetail, StatePropsOfMasterItem, coreReducer, DispatchPropsOfMultiEnumControl, Translator, OwnPropsOfLabel, LabelProps, ArrayTranslations } from '@jsonforms/core';
import React, { ComponentType, Dispatch, ReducerAction } from 'react';
export interface JsonFormsStateContext extends JsonFormsSubStates {
    dispatch?: Dispatch<ReducerAction<typeof coreReducer>>;
}
export declare const JsonFormsContext: React.Context<JsonFormsStateContext>;
export declare const JsonFormsStateProvider: ({ children, initState, onChange, middleware, }: any) => React.JSX.Element;
export declare const useJsonForms: () => JsonFormsStateContext;
export interface JsonFormsReduxContextProps extends JsonFormsSubStates {
    children: any;
    dispatch: Dispatch<ReducerAction<any>>;
}
export declare const ctxToArrayLayoutProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl) => import("@jsonforms/core").StatePropsOfArrayLayout;
export declare const ctxToArrayControlProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl) => import("@jsonforms/core").StatePropsOfArrayControl;
export declare const ctxToLayoutProps: (ctx: JsonFormsStateContext, props: OwnPropsOfLayout) => LayoutProps;
export declare const ctxToControlProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl) => import("@jsonforms/core").StatePropsOfControl;
export declare const ctxToEnumControlProps: (ctx: JsonFormsStateContext, props: OwnPropsOfEnum) => {
    options: import("@jsonforms/core").EnumOption[];
    cells?: {
        tester: import("@jsonforms/core").RankedTester;
        cell: any;
    }[];
    label: string;
    description?: string;
    required?: boolean;
    i18nKeyPrefix?: string;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    data: any;
    rootSchema: import("@jsonforms/core").JsonSchema;
    id: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    path: string;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
};
export declare const ctxToOneOfEnumControlProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl & OwnPropsOfEnum) => {
    options: import("@jsonforms/core").EnumOption[];
    cells?: {
        tester: import("@jsonforms/core").RankedTester;
        cell: any;
    }[];
    label: string;
    description?: string;
    required?: boolean;
    i18nKeyPrefix?: string;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    data: any;
    rootSchema: import("@jsonforms/core").JsonSchema;
    id: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    path: string;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
};
export declare const ctxToMultiEnumControlProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl) => {
    options: import("@jsonforms/core").EnumOption[];
    cells?: {
        tester: import("@jsonforms/core").RankedTester;
        cell: any;
    }[];
    label: string;
    description?: string;
    required?: boolean;
    i18nKeyPrefix?: string;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    data: any;
    rootSchema: import("@jsonforms/core").JsonSchema;
    id: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    path: string;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
};
export declare const ctxToControlWithDetailProps: (ctx: JsonFormsStateContext, props: OwnPropsOfControl) => StatePropsOfControlWithDetail;
export declare const ctxToAllOfProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfControl) => {
    rootSchema: import("@jsonforms/core").JsonSchema;
    path: string;
    id: string;
    indexOfFittingSchema: number;
    uischemas: import("@jsonforms/core").JsonFormsUISchemaRegistryEntry[];
    data: any;
    cells?: {
        tester: import("@jsonforms/core").RankedTester;
        cell: any;
    }[];
    label: string;
    description?: string;
    required?: boolean;
    i18nKeyPrefix?: string;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
};
export declare const ctxDispatchToControlProps: (dispatch: Dispatch<ReducerAction<any>>) => DispatchPropsOfControl;
export declare const ctxToAnyOfProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfControl) => CombinatorRendererProps;
export declare const ctxToOneOfProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfControl) => CombinatorRendererProps;
export declare const ctxToJsonFormsRendererProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfJsonFormsRenderer) => import("@jsonforms/core").StatePropsOfJsonFormsRenderer;
export declare const ctxDispatchToArrayControlProps: (dispatch: Dispatch<ReducerAction<any>>) => {
    addItem(path: string, value: any): () => void;
    removeItems?(path: string, toDelete: number[]): () => void;
    moveUp?(path: string, toMove: number): () => void;
    moveDown?(path: string, toMove: number): () => void;
    handleChange(path: string, value: any): void;
};
export declare const ctxToMasterListItemProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfMasterListItem) => StatePropsOfMasterItem;
export declare const ctxToCellProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfCell) => import("@jsonforms/core").StatePropsOfCell;
export declare const ctxToEnumCellProps: (ctx: JsonFormsStateContext, ownProps: EnumCellProps) => {
    options: import("@jsonforms/core").EnumOption[];
    isValid: boolean;
    rootSchema: import("@jsonforms/core").JsonSchema;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    data: any;
    id: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    path: string;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
    cells?: import("@jsonforms/core").JsonFormsCellRendererRegistryEntry[];
};
export declare const ctxToOneOfEnumCellProps: (ctx: JsonFormsStateContext, props: OwnPropsOfEnumCell) => {
    options: import("@jsonforms/core").EnumOption[];
    isValid: boolean;
    rootSchema: import("@jsonforms/core").JsonSchema;
    uischema: import("@jsonforms/core").ControlElement;
    errors: string;
    data: any;
    id: string;
    config?: any;
    schema: import("@jsonforms/core").JsonSchema;
    enabled: boolean;
    visible: boolean;
    path: string;
    renderers?: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
    cells?: import("@jsonforms/core").JsonFormsCellRendererRegistryEntry[];
};
export declare const ctxToDispatchCellProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfCell) => import("@jsonforms/core").DispatchCellStateProps;
export declare const ctxDispatchToMultiEnumProps: (dispatch: Dispatch<ReducerAction<any>>) => {
    addItem: (path: string, value: any) => void;
    removeItem?: (path: string, toDelete: any) => void;
    handleChange(path: string, value: any): void;
};
export declare const ctxToLabelProps: (ctx: JsonFormsStateContext, ownProps: OwnPropsOfLabel) => {
    text: string;
    visible: boolean;
    config: any;
    renderers: import("@jsonforms/core").JsonFormsRendererRegistryEntry[];
    cells: import("@jsonforms/core").JsonFormsCellRendererRegistryEntry[];
    uischema: import("@jsonforms/core").LabelElement;
};
interface WithContext {
    ctx: JsonFormsStateContext;
}
export declare const withJsonFormsContext: (Component: ComponentType<WithContext & any>) => ComponentType<any>;
export declare const withContextToJsonFormsRendererProps: (Component: ComponentType<JsonFormsProps>) => ComponentType<OwnPropsOfJsonFormsRenderer>;
export declare const withJsonFormsRendererProps: (Component: ComponentType<JsonFormsProps>, memoize?: boolean) => ComponentType<OwnPropsOfJsonFormsRenderer>;
export declare const withJsonFormsControlProps: (Component: ComponentType<ControlProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsLayoutProps: <T extends LayoutProps>(Component: ComponentType<T>, memoize?: boolean) => ComponentType<T & OwnPropsOfLayout>;
export declare const withJsonFormsOneOfProps: (Component: ComponentType<CombinatorRendererProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsAnyOfProps: (Component: ComponentType<CombinatorRendererProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsAllOfProps: (Component: ComponentType<CombinatorRendererProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsDetailProps: (Component: ComponentType<StatePropsOfControlWithDetail>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsArrayLayoutProps: (Component: ComponentType<ArrayLayoutProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsArrayControlProps: (Component: ComponentType<ArrayControlProps>, memoize?: boolean) => ComponentType<OwnPropsOfControl>;
export declare const withJsonFormsMasterListItemProps: (Component: ComponentType<StatePropsOfMasterItem>, memoize?: boolean) => ComponentType<OwnPropsOfMasterListItem>;
export declare const withJsonFormsCellProps: (Component: ComponentType<CellProps>, memoize?: boolean) => ComponentType<OwnPropsOfCell>;
export declare const withJsonFormsDispatchCellProps: (Component: ComponentType<DispatchCellProps>, memoize?: boolean) => ComponentType<OwnPropsOfCell>;
export declare const withJsonFormsEnumCellProps: (Component: ComponentType<EnumCellProps>, memoize?: boolean) => ComponentType<OwnPropsOfEnumCell>;
export declare const withJsonFormsEnumProps: (Component: ComponentType<ControlProps & OwnPropsOfEnum>, memoize?: boolean) => ComponentType<OwnPropsOfControl & OwnPropsOfEnum>;
export declare const withJsonFormsOneOfEnumCellProps: (Component: ComponentType<EnumCellProps>, memoize?: boolean) => ComponentType<OwnPropsOfEnumCell>;
export declare const withJsonFormsOneOfEnumProps: (Component: ComponentType<ControlProps & OwnPropsOfEnum>, memoize?: boolean) => ComponentType<OwnPropsOfControl & OwnPropsOfEnum>;
export declare const withJsonFormsMultiEnumProps: (Component: ComponentType<ControlProps & OwnPropsOfEnum & DispatchPropsOfMultiEnumControl>, memoize?: boolean) => ComponentType<OwnPropsOfControl & OwnPropsOfEnum & DispatchPropsOfMultiEnumControl>;
export declare const withJsonFormsLabelProps: (Component: ComponentType<LabelProps & OwnPropsOfEnum>, memoize?: boolean) => ComponentType<OwnPropsOfLabel>;
export interface TranslateProps {
    t: Translator;
    locale: string;
}
export declare const withTranslateProps: <P extends {}>(Component: ComponentType<TranslateProps & P>) => (props: P) => React.JSX.Element;
export declare const withArrayTranslationProps: <P extends ArrayLayoutProps>(Component: ComponentType<P & {
    translations: ArrayTranslations;
}>) => (props: P & TranslateProps) => React.JSX.Element;
export {};
