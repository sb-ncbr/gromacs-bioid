import { JsonFormsCellRendererRegistryEntry, JsonFormsRendererRegistryEntry } from '@jsonforms/core';
export * from './additional';
export * from './cells';
export * from './complex';
export * from './controls';
export * from './layouts';
export * from './mui-controls';
export * from './util';
export declare const materialRenderers: JsonFormsRendererRegistryEntry[];
export declare const materialCells: JsonFormsCellRendererRegistryEntry[];
export declare const Unwrapped: {
    ExpandPanelRenderer: import("react").MemoExoticComponent<(props: import("./layouts/ExpandPanelRenderer").ExpandPanelProps) => import("react").JSX.Element>;
    MaterialArrayLayout: ({ visible, addItem, translations, ...props }: import("@jsonforms/core").ArrayLayoutProps & {
        translations: import("@jsonforms/core").ArrayTranslations;
    }) => import("react").JSX.Element;
    MaterialCategorizationLayout: (props: import("./layouts/MaterialCategorizationLayout").MaterialCategorizationLayoutRendererProps) => import("react").JSX.Element;
    MaterialGroupLayout: ({ uischema, schema, path, visible, enabled, renderers, cells, direction, label, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
    MaterialHorizontalLayout: ({ uischema, renderers, cells, schema, path, enabled, visible, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
    MaterialVerticalLayout: ({ uischema, schema, path, enabled, visible, renderers, cells, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
    MaterialAnyOfStringOrEnumControl: typeof import("./controls/MaterialAnyOfStringOrEnumControl").MaterialAnyOfStringOrEnumControl;
    MaterialBooleanControl: ({ data, visible, label, id, enabled, uischema, schema, rootSchema, handleChange, errors, path, config, description, }: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialBooleanToggleControl: ({ data, visible, label, id, enabled, uischema, schema, rootSchema, handleChange, errors, path, config, description, }: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialDateControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialDateTimeControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialEnumControl: (props: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum & import("./mui-controls").WithOptionLabel & import("@jsonforms/react").TranslateProps) => import("react").JSX.Element;
    MaterialIntegerControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialNativeControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialNumberControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialOneOfEnumControl: (props: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum & import("./mui-controls").WithOptionLabel & import("@jsonforms/react").TranslateProps) => import("react").JSX.Element;
    MaterialOneOfRadioGroupControl: (props: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum) => import("react").JSX.Element;
    MaterialSliderControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialRadioGroupControl: (props: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum) => import("react").JSX.Element;
    MaterialTextControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialTimeControl: (props: import("@jsonforms/core").ControlProps) => import("react").JSX.Element;
    MaterialAllOfRenderer: ({ schema, rootSchema, visible, renderers, cells, path, uischemas, uischema, }: import("@jsonforms/core").StatePropsOfCombinator) => import("react").JSX.Element;
    MaterialAnyOfRenderer: ({ handleChange, schema, rootSchema, indexOfFittingSchema, visible, path, renderers, cells, uischema, uischemas, id, data, }: import("@jsonforms/core").CombinatorRendererProps) => import("react").JSX.Element;
    MaterialArrayControlRenderer: (props: import("@jsonforms/core").ArrayLayoutProps & {
        translations: import("@jsonforms/core").ArrayTranslations;
    }) => import("react").JSX.Element;
    MaterialEnumArrayRenderer: ({ config, id, schema, visible, errors, description, label, required, path, options, data, addItem, removeItem, handleChange: _handleChange, ...otherProps }: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum & import("@jsonforms/core").DispatchPropsOfMultiEnumControl) => import("react").JSX.Element;
    MaterialObjectRenderer: ({ renderers, cells, uischemas, schema, label, path, visible, enabled, uischema, rootSchema, }: import("@jsonforms/core").StatePropsOfControlWithDetail) => import("react").JSX.Element;
    MaterialOneOfRenderer: ({ handleChange, schema, path, renderers, cells, rootSchema, id, visible, indexOfFittingSchema, uischema, uischemas, data, }: import("@jsonforms/core").CombinatorRendererProps) => import("react").JSX.Element;
    MaterialLabelRenderer: ({ text, visible }: import("@jsonforms/core").LabelProps) => import("react").JSX.Element;
    MaterialListWithDetailRenderer: ({ uischemas, schema, uischema, path, enabled, errors, visible, label, required, removeItems, addItem, data, renderers, cells, config, rootSchema, description, disableAdd, disableRemove, translations, }: import("@jsonforms/core").ArrayLayoutProps & {
        translations: import("@jsonforms/core").ArrayTranslations;
    }) => import("react").JSX.Element;
};
