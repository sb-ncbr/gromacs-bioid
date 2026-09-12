export declare const UnwrappedComplex: {
    MaterialAllOfRenderer: ({ schema, rootSchema, visible, renderers, cells, path, uischemas, uischema, }: import("@jsonforms/core").StatePropsOfCombinator) => import("react").JSX.Element;
    MaterialAnyOfRenderer: ({ handleChange, schema, rootSchema, indexOfFittingSchema, visible, path, renderers, cells, uischema, uischemas, id, data, }: import("@jsonforms/core").CombinatorRendererProps) => import("react").JSX.Element;
    MaterialArrayControlRenderer: (props: import("@jsonforms/core").ArrayLayoutProps & {
        translations: import("@jsonforms/core").ArrayTranslations;
    }) => import("react").JSX.Element;
    MaterialEnumArrayRenderer: ({ config, id, schema, visible, errors, description, label, required, path, options, data, addItem, removeItem, handleChange: _handleChange, ...otherProps }: import("@jsonforms/core").ControlProps & import("@jsonforms/core").OwnPropsOfEnum & import("@jsonforms/core").DispatchPropsOfMultiEnumControl) => import("react").JSX.Element;
    MaterialObjectRenderer: ({ renderers, cells, uischemas, schema, label, path, visible, enabled, uischema, rootSchema, }: import("@jsonforms/core").StatePropsOfControlWithDetail) => import("react").JSX.Element;
    MaterialOneOfRenderer: ({ handleChange, schema, path, renderers, cells, rootSchema, id, visible, indexOfFittingSchema, uischema, uischemas, data, }: import("@jsonforms/core").CombinatorRendererProps) => import("react").JSX.Element;
};
