import React, { Component, useRef, useState, useEffect, useReducer, useCallback, useMemo, useContext } from 'react';
import maxBy from 'lodash/maxBy';
import { defaultMiddleware, Actions, coreReducer, configReducer, i18nReducer, mapStateToArrayLayoutProps, mapStateToArrayControlProps, mapStateToLayoutProps, mapStateToControlProps, mapStateToEnumControlProps, mapStateToOneOfEnumControlProps, mapStateToMultiEnumControlProps, mapStateToControlWithDetailProps, mapStateToAllOfProps, mapDispatchToControlProps, mapStateToAnyOfProps, mapStateToOneOfProps, mapStateToJsonFormsRendererProps, mapDispatchToArrayControlProps, mapStateToMasterListItemProps, mapStateToCellProps, defaultMapStateToEnumCellProps, mapStateToOneOfEnumCellProps, mapStateToDispatchCellProps, mapDispatchToMultiEnumProps, mapStateToLabelProps, defaultJsonFormsI18nState, getArrayTranslations, arrayDefaultTranslations, isControl, createId, removeId, Generate } from '@jsonforms/core';
import debounce from 'lodash/debounce';

class RendererComponent extends React.Component {
    constructor(props) {
        super(props);
    }
}

class Control extends RendererComponent {
    constructor(props) {
        super(props);
        this.handleChange = (value) => {
            this.setState({ value });
            this.updateData(value);
        };
        this.onFocus = () => {
            this.setState({ isFocused: true });
        };
        this.onBlur = () => {
            this.setState({ isFocused: false });
        };
        this.updateData = (value) => {
            this.props.handleChange(this.props.path, value);
        };
        this.state = {
            value: props.data ? props.data : '',
            isFocused: false,
        };
    }
}

class UnknownRenderer extends Component {
    render() {
        return (React.createElement("div", { style: { color: 'red' } },
            "No applicable ",
            this.props.type,
            " found."));
    }
}

const initialCoreState = {
    data: {},
    schema: {},
    uischema: undefined,
    errors: [],
    additionalErrors: [],
    validator: undefined,
    ajv: undefined,
};
const JsonFormsContext = React.createContext({
    core: initialCoreState,
    renderers: [],
});
const useEffectAfterFirstRender = (effect, dependencies) => {
    const firstExecution = useRef(true);
    useEffect(() => {
        if (firstExecution.current) {
            firstExecution.current = false;
            return;
        }
        effect();
    }, dependencies);
};
const JsonFormsStateProvider = ({ children, initState, onChange, middleware, }) => {
    const { data, schema, uischema, ajv, validationMode, additionalErrors } = initState.core;
    const middlewareRef = useRef(middleware ?? defaultMiddleware);
    middlewareRef.current = middleware ?? defaultMiddleware;
    const [core, setCore] = useState(() => middlewareRef.current(initState.core, Actions.init(data, schema, uischema, {
        ajv,
        validationMode,
        additionalErrors,
    }), coreReducer));
    useEffect(() => setCore((currentCore) => middlewareRef.current(currentCore, Actions.updateCore(data, schema, uischema, {
        ajv,
        validationMode,
        additionalErrors,
    }), coreReducer)), [data, schema, uischema, ajv, validationMode, additionalErrors]);
    const [config, configDispatch] = useReducer(configReducer, undefined, () => configReducer(undefined, Actions.setConfig(initState.config)));
    useEffectAfterFirstRender(() => {
        configDispatch(Actions.setConfig(initState.config));
    }, [initState.config]);
    const [i18n, i18nDispatch] = useReducer(i18nReducer, undefined, () => i18nReducer(initState.i18n, Actions.updateI18n(initState.i18n?.locale, initState.i18n?.translate, initState.i18n?.translateError)));
    useEffect(() => {
        i18nDispatch(Actions.updateI18n(initState.i18n?.locale, initState.i18n?.translate, initState.i18n?.translateError));
    }, [
        initState.i18n?.locale,
        initState.i18n?.translate,
        initState.i18n?.translateError,
    ]);
    const dispatch = useCallback((action) => {
        setCore((currentCore) => middlewareRef.current(currentCore, action, coreReducer));
    }, []);
    const contextValue = useMemo(() => ({
        core,
        renderers: initState.renderers,
        cells: initState.cells,
        config: config,
        uischemas: initState.uischemas,
        readonly: initState.readonly,
        i18n: i18n,
        dispatch: dispatch,
    }), [
        core,
        initState.renderers,
        initState.cells,
        config,
        initState.uischemas,
        initState.readonly,
        i18n,
    ]);
    const onChangeRef = useRef(onChange);
    useEffect(() => {
        onChangeRef.current = onChange;
    }, [onChange]);
    const debouncedEmit = useCallback(debounce((...args) => onChangeRef.current?.(...args), 10), []);
    useEffect(() => {
        debouncedEmit({ data: core.data, errors: core.errors });
    }, [core.data, core.errors]);
    return (React.createElement(JsonFormsContext.Provider, { value: contextValue }, children));
};
const useJsonForms = () => useContext(JsonFormsContext);
const ctxToArrayLayoutProps = (ctx, props) => mapStateToArrayLayoutProps({ jsonforms: { ...ctx } }, props);
const ctxToArrayControlProps = (ctx, props) => mapStateToArrayControlProps({ jsonforms: { ...ctx } }, props);
const ctxToLayoutProps = (ctx, props) => mapStateToLayoutProps({ jsonforms: { ...ctx } }, props);
const ctxToControlProps = (ctx, props) => mapStateToControlProps({ jsonforms: { ...ctx } }, props);
const ctxToEnumControlProps = (ctx, props) => {
    const enumProps = mapStateToEnumControlProps({ jsonforms: { ...ctx } }, props);
    const options = useMemo(() => enumProps.options, [props.options, enumProps.schema, ctx.i18n?.translate]);
    return { ...enumProps, options };
};
const ctxToOneOfEnumControlProps = (ctx, props) => {
    const enumProps = mapStateToOneOfEnumControlProps({ jsonforms: { ...ctx } }, props);
    const options = useMemo(() => enumProps.options, [props.options, enumProps.schema, ctx.i18n?.translate]);
    return { ...enumProps, options };
};
const ctxToMultiEnumControlProps = (ctx, props) => {
    const enumProps = mapStateToMultiEnumControlProps({ jsonforms: { ...ctx } }, props);
    const options = useMemo(() => enumProps.options, [enumProps.schema, ctx.i18n?.translate]);
    return { ...enumProps, options };
};
const ctxToControlWithDetailProps = (ctx, props) => mapStateToControlWithDetailProps({ jsonforms: { ...ctx } }, props);
const ctxToAllOfProps = (ctx, ownProps) => {
    const props = mapStateToAllOfProps({ jsonforms: { ...ctx } }, ownProps);
    return {
        ...props,
    };
};
const ctxDispatchToControlProps = (dispatch) => useMemo(() => mapDispatchToControlProps(dispatch), [dispatch]);
const ctxToAnyOfProps = (ctx, ownProps) => {
    const props = mapStateToAnyOfProps({ jsonforms: { ...ctx } }, ownProps);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return {
        ...props,
        ...dispatchProps,
    };
};
const ctxToOneOfProps = (ctx, ownProps) => {
    const props = mapStateToOneOfProps({ jsonforms: { ...ctx } }, ownProps);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return {
        ...props,
        ...dispatchProps,
    };
};
const ctxToJsonFormsRendererProps = (ctx, ownProps) => mapStateToJsonFormsRendererProps({ jsonforms: { ...ctx } }, ownProps);
const ctxDispatchToArrayControlProps = (dispatch) => ({
    ...ctxDispatchToControlProps(dispatch),
    ...useMemo(() => mapDispatchToArrayControlProps(dispatch), [dispatch]),
});
const ctxToMasterListItemProps = (ctx, ownProps) => mapStateToMasterListItemProps({ jsonforms: { ...ctx } }, ownProps);
const ctxToCellProps = (ctx, ownProps) => {
    return mapStateToCellProps({ jsonforms: { ...ctx } }, ownProps);
};
const ctxToEnumCellProps = (ctx, ownProps) => {
    const cellProps = defaultMapStateToEnumCellProps({ jsonforms: { ...ctx } }, ownProps);
    const options = useMemo(() => cellProps.options, [ownProps.options, cellProps.schema, ctx.i18n?.translate]);
    return { ...cellProps, options };
};
const ctxToOneOfEnumCellProps = (ctx, props) => {
    const enumCellProps = mapStateToOneOfEnumCellProps({ jsonforms: { ...ctx } }, props);
    const options = useMemo(() => enumCellProps.options, [props.options, enumCellProps.schema, ctx.i18n?.translate]);
    return { ...enumCellProps, options };
};
const ctxToDispatchCellProps = (ctx, ownProps) => {
    return mapStateToDispatchCellProps({ jsonforms: { ...ctx } }, ownProps);
};
const ctxDispatchToMultiEnumProps = (dispatch) => ({
    ...ctxDispatchToControlProps(dispatch),
    ...useMemo(() => mapDispatchToMultiEnumProps(dispatch), [dispatch]),
});
const ctxToLabelProps = (ctx, ownProps) => {
    return mapStateToLabelProps({ jsonforms: { ...ctx } }, ownProps);
};
const withJsonFormsContext = (Component) => function WithJsonFormsContext(props) {
    const ctx = useJsonForms();
    return React.createElement(Component, { ctx: ctx, props: props });
};
const withContextToJsonFormsRendererProps = (Component) => function WithContextToJsonFormsRendererProps({ ctx, props, }) {
    const contextProps = ctxToJsonFormsRendererProps(ctx, props);
    return React.createElement(Component, { ...props, ...contextProps });
};
const withContextToControlProps = (Component) => function WithContextToControlProps({ ctx, props, }) {
    const controlProps = ctxToControlProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...controlProps, ...dispatchProps });
};
const withContextToLayoutProps = (Component) => function WithContextToLayoutProps({ ctx, props, }) {
    const layoutProps = ctxToLayoutProps(ctx, props);
    return React.createElement(Component, { ...props, ...layoutProps });
};
const withContextToOneOfProps = (Component) => function WithContextToOneOfProps({ ctx, props, }) {
    const oneOfProps = ctxToOneOfProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...oneOfProps, ...dispatchProps });
};
const withContextToAnyOfProps = (Component) => function WithContextToAnyOfProps({ ctx, props, }) {
    const oneOfProps = ctxToAnyOfProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...oneOfProps, ...dispatchProps });
};
const withContextToAllOfProps = (Component) => function WithContextToAllOfProps({ ctx, props, }) {
    const allOfProps = ctxToAllOfProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...allOfProps, ...dispatchProps });
};
const withContextToDetailProps = (Component) => function WithContextToDetailProps({ ctx, props, }) {
    const detailProps = ctxToControlWithDetailProps(ctx, props);
    return React.createElement(Component, { ...props, ...detailProps });
};
const withContextToArrayLayoutProps = (Component) => function WithContextToArrayLayoutProps({ ctx, props, }) {
    const arrayLayoutProps = ctxToArrayLayoutProps(ctx, props);
    const dispatchProps = ctxDispatchToArrayControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...arrayLayoutProps, ...dispatchProps });
};
const withContextToArrayControlProps = (Component) => function WithContextToArrayControlProps({ ctx, props, }) {
    const stateProps = ctxToArrayControlProps(ctx, props);
    const dispatchProps = ctxDispatchToArrayControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...stateProps, ...dispatchProps });
};
const withContextToMasterListItemProps = (Component) => function WithContextToMasterListItemProps({ ctx, props, }) {
    const stateProps = ctxToMasterListItemProps(ctx, props);
    return React.createElement(Component, { ...props, ...stateProps });
};
const withContextToCellProps = (Component) => function WithContextToCellProps({ ctx, props, }) {
    const cellProps = ctxToCellProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...cellProps });
};
const withContextToDispatchCellProps = (Component) => function WithContextToDispatchCellProps({ ctx, props, }) {
    const cellProps = ctxToDispatchCellProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...cellProps });
};
const withContextToEnumCellProps = (Component) => function WithContextToEnumCellProps({ ctx, props, }) {
    const cellProps = ctxToEnumCellProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...cellProps });
};
const withContextToEnumProps = (Component) => function WithContextToEnumProps({ ctx, props, }) {
    const stateProps = ctxToEnumControlProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...stateProps });
};
const withContextToOneOfEnumCellProps = (Component) => function WithContextToOneOfEnumCellProps({ ctx, props, }) {
    const cellProps = ctxToOneOfEnumCellProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...cellProps });
};
const withContextToOneOfEnumProps = (Component) => function WithContextToOneOfEnumProps({ ctx, props, }) {
    const stateProps = ctxToOneOfEnumControlProps(ctx, props);
    const dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...stateProps });
};
const withContextToMultiEnumProps = (Component) => function WithContextToMultiEnumProps({ ctx, props, }) {
    const stateProps = ctxToMultiEnumControlProps(ctx, props);
    const dispatchProps = ctxDispatchToMultiEnumProps(ctx.dispatch);
    return React.createElement(Component, { ...props, ...dispatchProps, ...stateProps });
};
const withContextToLabelProps = (Component) => function WithContextToLabelProps({ ctx, props, }) {
    const stateProps = ctxToLabelProps(ctx, props);
    return React.createElement(Component, { ...props, ...stateProps });
};
const withJsonFormsRendererProps = (Component, memoize = true) => withJsonFormsContext(withContextToJsonFormsRendererProps(memoize ? React.memo(Component) : Component));
const withJsonFormsControlProps = (Component, memoize = true) => withJsonFormsContext(withContextToControlProps(memoize ? React.memo(Component) : Component));
const withJsonFormsLayoutProps = (Component, memoize = true) => withJsonFormsContext(withContextToLayoutProps(memoize ? React.memo(Component) : Component));
const withJsonFormsOneOfProps = (Component, memoize = true) => withJsonFormsContext(withContextToOneOfProps(memoize ? React.memo(Component) : Component));
const withJsonFormsAnyOfProps = (Component, memoize = true) => withJsonFormsContext(withContextToAnyOfProps(memoize ? React.memo(Component) : Component));
const withJsonFormsAllOfProps = (Component, memoize = true) => withJsonFormsContext(withContextToAllOfProps(memoize ? React.memo(Component) : Component));
const withJsonFormsDetailProps = (Component, memoize = true) => withJsonFormsContext(withContextToDetailProps(memoize ? React.memo(Component) : Component));
const withJsonFormsArrayLayoutProps = (Component, memoize = true) => withJsonFormsContext(withContextToArrayLayoutProps(memoize ? React.memo(Component) : Component));
const withJsonFormsArrayControlProps = (Component, memoize = true) => withJsonFormsContext(withContextToArrayControlProps(memoize ? React.memo(Component) : Component));
const withJsonFormsMasterListItemProps = (Component, memoize = true) => withJsonFormsContext(withContextToMasterListItemProps(memoize ? React.memo(Component) : Component));
const withJsonFormsCellProps = (Component, memoize = true) => withJsonFormsContext(withContextToCellProps(memoize ? React.memo(Component) : Component));
const withJsonFormsDispatchCellProps = (Component, memoize = true) => withJsonFormsContext(withContextToDispatchCellProps(memoize ? React.memo(Component) : Component));
const withJsonFormsEnumCellProps = (Component, memoize = true) => withJsonFormsContext(withContextToEnumCellProps(memoize ? React.memo(Component) : Component));
const withJsonFormsEnumProps = (Component, memoize = true) => withJsonFormsContext(withContextToEnumProps(memoize ? React.memo(Component) : Component));
const withJsonFormsOneOfEnumCellProps = (Component, memoize = true) => withJsonFormsContext(withContextToOneOfEnumCellProps(memoize ? React.memo(Component) : Component));
const withJsonFormsOneOfEnumProps = (Component, memoize = true) => withJsonFormsContext(withContextToOneOfEnumProps(memoize ? React.memo(Component) : Component));
const withJsonFormsMultiEnumProps = (Component, memoize = true) => withJsonFormsContext(withContextToMultiEnumProps(memoize ? React.memo(Component) : Component));
const withJsonFormsLabelProps = (Component, memoize = true) => withJsonFormsContext(withContextToLabelProps(memoize ? React.memo(Component) : Component));
const withTranslateProps = (Component) => function WithTranslateProps(props) {
    const ctx = useJsonForms();
    const locale = ctx.i18n?.locale ?? defaultJsonFormsI18nState.locale;
    const t = ctx.i18n?.translate ?? defaultJsonFormsI18nState.translate;
    return React.createElement(Component, { ...props, locale: locale, t: t });
};
const withArrayTranslationProps = (Component) => function withArrayTranslatationProps(props) {
    const translations = useMemo(() => getArrayTranslations(props.t, arrayDefaultTranslations, props.i18nKeyPrefix, props.label), [props.t, props.i18nKeyPrefix, props.label]);
    return React.createElement(Component, { ...props, translations: translations });
};

class JsonFormsDispatchRenderer extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            id: isControl(props.uischema)
                ? createId(props.uischema.scope)
                : undefined,
        };
    }
    componentWillUnmount() {
        if (isControl(this.props.uischema)) {
            removeId(this.state.id);
        }
    }
    componentDidUpdate(prevProps) {
        if (prevProps.schema !== this.props.schema) {
            removeId(this.state.id);
            this.setState({
                id: isControl(this.props.uischema)
                    ? createId(this.props.uischema.scope)
                    : undefined,
            });
        }
    }
    render() {
        const { schema, rootSchema, uischema, path, enabled, renderers, cells, config, } = this.props;
        return (React.createElement(TestAndRender, { uischema: uischema, schema: schema, rootSchema: rootSchema, path: path, enabled: enabled, renderers: renderers, cells: cells, id: this.state.id, config: config }));
    }
}
const TestAndRender = React.memo(function TestAndRender(props) {
    const testerContext = useMemo(() => ({
        rootSchema: props.rootSchema,
        config: props.config,
    }), [props.rootSchema, props.config]);
    const renderer = useMemo(() => maxBy(props.renderers, (r) => r.tester(props.uischema, props.schema, testerContext)), [props.renderers, props.uischema, props.schema, testerContext]);
    if (renderer === undefined ||
        renderer.tester(props.uischema, props.schema, testerContext) === -1) {
        return React.createElement(UnknownRenderer, { type: 'renderer' });
    }
    else {
        const Render = renderer.renderer;
        return (React.createElement(Render, { uischema: props.uischema, schema: props.schema, path: props.path, enabled: props.enabled, renderers: props.renderers, cells: props.cells, id: props.id }));
    }
});
class ResolvedJsonFormsDispatchRenderer extends JsonFormsDispatchRenderer {
    constructor(props) {
        super(props);
    }
}
const JsonFormsDispatch = withJsonFormsRendererProps(JsonFormsDispatchRenderer);
const ResolvedJsonFormsDispatch = withJsonFormsRendererProps(ResolvedJsonFormsDispatchRenderer);
const JsonForms = (props) => {
    const { ajv, data, schema, uischema, renderers, cells, onChange, config, uischemas, readonly, validationMode, i18n, additionalErrors, middleware, } = props;
    const schemaToUse = useMemo(() => (schema !== undefined ? schema : Generate.jsonSchema(data)), [schema, data]);
    const uischemaToUse = useMemo(() => typeof uischema === 'object'
        ? uischema
        : Generate.uiSchema(schemaToUse, undefined, undefined, schemaToUse), [uischema, schemaToUse]);
    return (React.createElement(JsonFormsStateProvider, { initState: {
            core: {
                ajv,
                data,
                schema: schemaToUse,
                uischema: uischemaToUse,
                validationMode: validationMode,
                additionalErrors: additionalErrors,
            },
            config,
            uischemas,
            renderers,
            cells,
            readonly,
            i18n,
        }, onChange: onChange, middleware: middleware },
        React.createElement(JsonFormsDispatch, null)));
};

const Dispatch = ({ uischema, schema, rootSchema, path, cells, id, enabled, renderers, config, }) => {
    const testerContext = useMemo(() => ({
        rootSchema: rootSchema,
        config: config,
    }), [rootSchema, config]);
    const cell = useMemo(() => maxBy(cells, (r) => r.tester(uischema, schema, testerContext)), [cells, uischema, schema, testerContext]);
    if (cell === undefined ||
        cell.tester(uischema, schema, testerContext) === -1) {
        return React.createElement(UnknownRenderer, { type: 'cell' });
    }
    else {
        const Cell = cell.cell;
        return (React.createElement(Cell, { uischema: uischema, schema: schema, enabled: enabled, path: path, id: id, renderers: renderers, cells: cells }));
    }
};
const DispatchCell = withJsonFormsDispatchCellProps(Dispatch);

export { Control, Dispatch, DispatchCell, JsonForms, JsonFormsContext, JsonFormsDispatch, JsonFormsDispatchRenderer, JsonFormsStateProvider, RendererComponent, ResolvedJsonFormsDispatch, ResolvedJsonFormsDispatchRenderer, UnknownRenderer, ctxDispatchToArrayControlProps, ctxDispatchToControlProps, ctxDispatchToMultiEnumProps, ctxToAllOfProps, ctxToAnyOfProps, ctxToArrayControlProps, ctxToArrayLayoutProps, ctxToCellProps, ctxToControlProps, ctxToControlWithDetailProps, ctxToDispatchCellProps, ctxToEnumCellProps, ctxToEnumControlProps, ctxToJsonFormsRendererProps, ctxToLabelProps, ctxToLayoutProps, ctxToMasterListItemProps, ctxToMultiEnumControlProps, ctxToOneOfEnumCellProps, ctxToOneOfEnumControlProps, ctxToOneOfProps, useJsonForms, withArrayTranslationProps, withContextToJsonFormsRendererProps, withJsonFormsAllOfProps, withJsonFormsAnyOfProps, withJsonFormsArrayControlProps, withJsonFormsArrayLayoutProps, withJsonFormsCellProps, withJsonFormsContext, withJsonFormsControlProps, withJsonFormsDetailProps, withJsonFormsDispatchCellProps, withJsonFormsEnumCellProps, withJsonFormsEnumProps, withJsonFormsLabelProps, withJsonFormsLayoutProps, withJsonFormsMasterListItemProps, withJsonFormsMultiEnumProps, withJsonFormsOneOfEnumCellProps, withJsonFormsOneOfEnumProps, withJsonFormsOneOfProps, withJsonFormsRendererProps, withTranslateProps };
//# sourceMappingURL=jsonforms-react.esm.js.map
