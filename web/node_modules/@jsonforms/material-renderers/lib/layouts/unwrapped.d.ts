export declare const UnwrappedLayouts: {
    ExpandPanelRenderer: import("react").MemoExoticComponent<(props: import("./ExpandPanelRenderer").ExpandPanelProps) => import("react").JSX.Element>;
    MaterialArrayLayout: ({ visible, addItem, translations, ...props }: import("@jsonforms/core").ArrayLayoutProps & {
        translations: import("@jsonforms/core").ArrayTranslations;
    }) => import("react").JSX.Element;
    MaterialCategorizationLayout: (props: import("./MaterialCategorizationLayout").MaterialCategorizationLayoutRendererProps) => import("react").JSX.Element;
    MaterialGroupLayout: ({ uischema, schema, path, visible, enabled, renderers, cells, direction, label, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
    MaterialHorizontalLayout: ({ uischema, renderers, cells, schema, path, enabled, visible, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
    MaterialVerticalLayout: ({ uischema, schema, path, enabled, visible, renderers, cells, }: import("@jsonforms/core").LayoutProps) => import("react").JSX.Element;
};
export * from './ArrayToolbar';
