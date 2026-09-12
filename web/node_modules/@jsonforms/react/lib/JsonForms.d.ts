import React, { ComponentType } from 'react';
import type Ajv from 'ajv';
import type { ErrorObject } from 'ajv';
import { JsonFormsCellRendererRegistryEntry, JsonFormsCore, JsonFormsI18nState, JsonFormsProps, JsonFormsRendererRegistryEntry, JsonFormsUISchemaRegistryEntry, JsonSchema, Middleware, OwnPropsOfJsonFormsRenderer, UISchemaElement, ValidationMode } from '@jsonforms/core';
interface JsonFormsRendererState {
    id: string;
}
export interface JsonFormsReactProps {
    onChange?(state: Pick<JsonFormsCore, 'data' | 'errors'>): void;
    middleware?: Middleware;
}
export declare class JsonFormsDispatchRenderer extends React.Component<JsonFormsProps, JsonFormsRendererState> {
    constructor(props: JsonFormsProps);
    componentWillUnmount(): void;
    componentDidUpdate(prevProps: JsonFormsProps): void;
    render(): React.JSX.Element;
}
/**
 * @deprecated Since Version 3.0 this optimization renderer is no longer necessary.
 * Use `JsonFormsDispatch` instead.
 * We still export it for backward compatibility
 */
export declare class ResolvedJsonFormsDispatchRenderer extends JsonFormsDispatchRenderer {
    constructor(props: JsonFormsProps);
}
export declare const JsonFormsDispatch: ComponentType<OwnPropsOfJsonFormsRenderer>;
/**
 * @deprecated Since Version 3.0 this optimization component is no longer necessary.
 * Use `JsonFormsDispatch` instead.
 * We still export it for backward compatibility
 */
export declare const ResolvedJsonFormsDispatch: ComponentType<OwnPropsOfJsonFormsRenderer>;
export interface JsonFormsInitStateProps {
    data: any;
    schema?: JsonSchema;
    uischema?: UISchemaElement;
    renderers: JsonFormsRendererRegistryEntry[];
    cells?: JsonFormsCellRendererRegistryEntry[];
    ajv?: Ajv;
    config?: any;
    uischemas?: JsonFormsUISchemaRegistryEntry[];
    readonly?: boolean;
    validationMode?: ValidationMode;
    i18n?: JsonFormsI18nState;
    additionalErrors?: ErrorObject[];
}
export declare const JsonForms: (props: JsonFormsInitStateProps & JsonFormsReactProps) => React.JSX.Element;
export {};
