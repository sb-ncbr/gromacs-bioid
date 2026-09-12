import React, { ComponentType } from 'react';
import type Ajv from 'ajv';
import type { UISchemaElement } from '@jsonforms/core';
import { JsonFormsCellRendererRegistryEntry, JsonFormsRendererRegistryEntry, JsonSchema, OwnPropsOfRenderer } from '@jsonforms/core';
export declare const renderLayoutElements: (elements: UISchemaElement[], schema: JsonSchema, path: string, enabled: boolean, renderers?: JsonFormsRendererRegistryEntry[], cells?: JsonFormsCellRendererRegistryEntry[]) => React.JSX.Element[];
export interface MaterialLayoutRendererProps extends OwnPropsOfRenderer {
    elements: UISchemaElement[];
    direction: 'row' | 'column';
}
export declare const MaterialLayoutRenderer: React.MemoExoticComponent<({ visible, elements, schema, path, enabled, direction, renderers, cells, }: MaterialLayoutRendererProps) => React.JSX.Element>;
export interface AjvProps {
    ajv: Ajv;
}
export declare const withAjvProps: <P extends {}>(Component: ComponentType<AjvProps & P>) => (props: P) => React.JSX.Element;
export interface MaterialLabelableLayoutRendererProps extends MaterialLayoutRendererProps {
    label?: string;
}
