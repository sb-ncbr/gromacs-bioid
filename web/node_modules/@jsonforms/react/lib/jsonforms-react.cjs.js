'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var React = require('react');
var maxBy = require('lodash/maxBy');
var core = require('@jsonforms/core');
var debounce = require('lodash/debounce');

function _interopDefaultLegacy (e) { return e && typeof e === 'object' && 'default' in e ? e : { 'default': e }; }

var React__default = /*#__PURE__*/_interopDefaultLegacy(React);
var maxBy__default = /*#__PURE__*/_interopDefaultLegacy(maxBy);
var debounce__default = /*#__PURE__*/_interopDefaultLegacy(debounce);

/******************************************************************************
Copyright (c) Microsoft Corporation.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
***************************************************************************** */
/* global Reflect, Promise, SuppressedError, Symbol */

var extendStatics = function(d, b) {
    extendStatics = Object.setPrototypeOf ||
        ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
        function (d, b) { for (var p in b) if (Object.prototype.hasOwnProperty.call(b, p)) d[p] = b[p]; };
    return extendStatics(d, b);
};

function __extends(d, b) {
    if (typeof b !== "function" && b !== null)
        throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
    extendStatics(d, b);
    function __() { this.constructor = d; }
    d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
}

var __assign = function() {
    __assign = Object.assign || function __assign(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p)) t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};

function __spreadArray(to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
}

typeof SuppressedError === "function" ? SuppressedError : function (error, suppressed, message) {
    var e = new Error(message);
    return e.name = "SuppressedError", e.error = error, e.suppressed = suppressed, e;
};

var RendererComponent =  (function (_super) {
    __extends(RendererComponent, _super);
    function RendererComponent(props) {
        return _super.call(this, props) || this;
    }
    return RendererComponent;
}(React__default["default"].Component));

var Control =  (function (_super) {
    __extends(Control, _super);
    function Control(props) {
        var _this = _super.call(this, props) || this;
        _this.handleChange = function (value) {
            _this.setState({ value: value });
            _this.updateData(value);
        };
        _this.onFocus = function () {
            _this.setState({ isFocused: true });
        };
        _this.onBlur = function () {
            _this.setState({ isFocused: false });
        };
        _this.updateData = function (value) {
            _this.props.handleChange(_this.props.path, value);
        };
        _this.state = {
            value: props.data ? props.data : '',
            isFocused: false,
        };
        return _this;
    }
    return Control;
}(RendererComponent));

var UnknownRenderer =  (function (_super) {
    __extends(UnknownRenderer, _super);
    function UnknownRenderer() {
        return _super !== null && _super.apply(this, arguments) || this;
    }
    UnknownRenderer.prototype.render = function () {
        return (React__default["default"].createElement("div", { style: { color: 'red' } },
            "No applicable ",
            this.props.type,
            " found."));
    };
    return UnknownRenderer;
}(React.Component));

var initialCoreState = {
    data: {},
    schema: {},
    uischema: undefined,
    errors: [],
    additionalErrors: [],
    validator: undefined,
    ajv: undefined,
};
var JsonFormsContext = React__default["default"].createContext({
    core: initialCoreState,
    renderers: [],
});
var useEffectAfterFirstRender = function (effect, dependencies) {
    var firstExecution = React.useRef(true);
    React.useEffect(function () {
        if (firstExecution.current) {
            firstExecution.current = false;
            return;
        }
        effect();
    }, dependencies);
};
var JsonFormsStateProvider = function (_a) {
    var _b, _c, _d;
    var children = _a.children, initState = _a.initState, onChange = _a.onChange, middleware = _a.middleware;
    var _e = initState.core, data = _e.data, schema = _e.schema, uischema = _e.uischema, ajv = _e.ajv, validationMode = _e.validationMode, additionalErrors = _e.additionalErrors;
    var middlewareRef = React.useRef(middleware !== null && middleware !== void 0 ? middleware : core.defaultMiddleware);
    middlewareRef.current = middleware !== null && middleware !== void 0 ? middleware : core.defaultMiddleware;
    var _f = React.useState(function () {
        return middlewareRef.current(initState.core, core.Actions.init(data, schema, uischema, {
            ajv: ajv,
            validationMode: validationMode,
            additionalErrors: additionalErrors,
        }), core.coreReducer);
    }), core$1 = _f[0], setCore = _f[1];
    React.useEffect(function () {
        return setCore(function (currentCore) {
            return middlewareRef.current(currentCore, core.Actions.updateCore(data, schema, uischema, {
                ajv: ajv,
                validationMode: validationMode,
                additionalErrors: additionalErrors,
            }), core.coreReducer);
        });
    }, [data, schema, uischema, ajv, validationMode, additionalErrors]);
    var _g = React.useReducer(core.configReducer, undefined, function () {
        return core.configReducer(undefined, core.Actions.setConfig(initState.config));
    }), config = _g[0], configDispatch = _g[1];
    useEffectAfterFirstRender(function () {
        configDispatch(core.Actions.setConfig(initState.config));
    }, [initState.config]);
    var _h = React.useReducer(core.i18nReducer, undefined, function () {
        var _a, _b, _c;
        return core.i18nReducer(initState.i18n, core.Actions.updateI18n((_a = initState.i18n) === null || _a === void 0 ? void 0 : _a.locale, (_b = initState.i18n) === null || _b === void 0 ? void 0 : _b.translate, (_c = initState.i18n) === null || _c === void 0 ? void 0 : _c.translateError));
    }), i18n = _h[0], i18nDispatch = _h[1];
    React.useEffect(function () {
        var _a, _b, _c;
        i18nDispatch(core.Actions.updateI18n((_a = initState.i18n) === null || _a === void 0 ? void 0 : _a.locale, (_b = initState.i18n) === null || _b === void 0 ? void 0 : _b.translate, (_c = initState.i18n) === null || _c === void 0 ? void 0 : _c.translateError));
    }, [
        (_b = initState.i18n) === null || _b === void 0 ? void 0 : _b.locale,
        (_c = initState.i18n) === null || _c === void 0 ? void 0 : _c.translate,
        (_d = initState.i18n) === null || _d === void 0 ? void 0 : _d.translateError,
    ]);
    var dispatch = React.useCallback(function (action) {
        setCore(function (currentCore) {
            return middlewareRef.current(currentCore, action, core.coreReducer);
        });
    }, []);
    var contextValue = React.useMemo(function () { return ({
        core: core$1,
        renderers: initState.renderers,
        cells: initState.cells,
        config: config,
        uischemas: initState.uischemas,
        readonly: initState.readonly,
        i18n: i18n,
        dispatch: dispatch,
    }); }, [
        core$1,
        initState.renderers,
        initState.cells,
        config,
        initState.uischemas,
        initState.readonly,
        i18n,
    ]);
    var onChangeRef = React.useRef(onChange);
    React.useEffect(function () {
        onChangeRef.current = onChange;
    }, [onChange]);
    var debouncedEmit = React.useCallback(debounce__default["default"](function () {
        var _a;
        var args = [];
        for (var _i = 0; _i < arguments.length; _i++) {
            args[_i] = arguments[_i];
        }
        return (_a = onChangeRef.current) === null || _a === void 0 ? void 0 : _a.call.apply(_a, __spreadArray([onChangeRef], args, false));
    }, 10), []);
    React.useEffect(function () {
        debouncedEmit({ data: core$1.data, errors: core$1.errors });
    }, [core$1.data, core$1.errors]);
    return (React__default["default"].createElement(JsonFormsContext.Provider, { value: contextValue }, children));
};
var useJsonForms = function () {
    return React.useContext(JsonFormsContext);
};
var ctxToArrayLayoutProps = function (ctx, props) { return core.mapStateToArrayLayoutProps({ jsonforms: __assign({}, ctx) }, props); };
var ctxToArrayControlProps = function (ctx, props) { return core.mapStateToArrayControlProps({ jsonforms: __assign({}, ctx) }, props); };
var ctxToLayoutProps = function (ctx, props) { return core.mapStateToLayoutProps({ jsonforms: __assign({}, ctx) }, props); };
var ctxToControlProps = function (ctx, props) { return core.mapStateToControlProps({ jsonforms: __assign({}, ctx) }, props); };
var ctxToEnumControlProps = function (ctx, props) {
    var _a;
    var enumProps = core.mapStateToEnumControlProps({ jsonforms: __assign({}, ctx) }, props);
    var options = React.useMemo(function () { return enumProps.options; }, [props.options, enumProps.schema, (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.translate]);
    return __assign(__assign({}, enumProps), { options: options });
};
var ctxToOneOfEnumControlProps = function (ctx, props) {
    var _a;
    var enumProps = core.mapStateToOneOfEnumControlProps({ jsonforms: __assign({}, ctx) }, props);
    var options = React.useMemo(function () { return enumProps.options; }, [props.options, enumProps.schema, (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.translate]);
    return __assign(__assign({}, enumProps), { options: options });
};
var ctxToMultiEnumControlProps = function (ctx, props) {
    var _a;
    var enumProps = core.mapStateToMultiEnumControlProps({ jsonforms: __assign({}, ctx) }, props);
    var options = React.useMemo(function () { return enumProps.options; }, [enumProps.schema, (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.translate]);
    return __assign(__assign({}, enumProps), { options: options });
};
var ctxToControlWithDetailProps = function (ctx, props) {
    return core.mapStateToControlWithDetailProps({ jsonforms: __assign({}, ctx) }, props);
};
var ctxToAllOfProps = function (ctx, ownProps) {
    var props = core.mapStateToAllOfProps({ jsonforms: __assign({}, ctx) }, ownProps);
    return __assign({}, props);
};
var ctxDispatchToControlProps = function (dispatch) {
    return React.useMemo(function () { return core.mapDispatchToControlProps(dispatch); }, [dispatch]);
};
var ctxToAnyOfProps = function (ctx, ownProps) {
    var props = core.mapStateToAnyOfProps({ jsonforms: __assign({}, ctx) }, ownProps);
    var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return __assign(__assign({}, props), dispatchProps);
};
var ctxToOneOfProps = function (ctx, ownProps) {
    var props = core.mapStateToOneOfProps({ jsonforms: __assign({}, ctx) }, ownProps);
    var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
    return __assign(__assign({}, props), dispatchProps);
};
var ctxToJsonFormsRendererProps = function (ctx, ownProps) { return core.mapStateToJsonFormsRendererProps({ jsonforms: __assign({}, ctx) }, ownProps); };
var ctxDispatchToArrayControlProps = function (dispatch) { return (__assign(__assign({}, ctxDispatchToControlProps(dispatch)), React.useMemo(function () { return core.mapDispatchToArrayControlProps(dispatch); }, [dispatch]))); };
var ctxToMasterListItemProps = function (ctx, ownProps) { return core.mapStateToMasterListItemProps({ jsonforms: __assign({}, ctx) }, ownProps); };
var ctxToCellProps = function (ctx, ownProps) {
    return core.mapStateToCellProps({ jsonforms: __assign({}, ctx) }, ownProps);
};
var ctxToEnumCellProps = function (ctx, ownProps) {
    var _a;
    var cellProps = core.defaultMapStateToEnumCellProps({ jsonforms: __assign({}, ctx) }, ownProps);
    var options = React.useMemo(function () { return cellProps.options; }, [ownProps.options, cellProps.schema, (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.translate]);
    return __assign(__assign({}, cellProps), { options: options });
};
var ctxToOneOfEnumCellProps = function (ctx, props) {
    var _a;
    var enumCellProps = core.mapStateToOneOfEnumCellProps({ jsonforms: __assign({}, ctx) }, props);
    var options = React.useMemo(function () { return enumCellProps.options; }, [props.options, enumCellProps.schema, (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.translate]);
    return __assign(__assign({}, enumCellProps), { options: options });
};
var ctxToDispatchCellProps = function (ctx, ownProps) {
    return core.mapStateToDispatchCellProps({ jsonforms: __assign({}, ctx) }, ownProps);
};
var ctxDispatchToMultiEnumProps = function (dispatch) { return (__assign(__assign({}, ctxDispatchToControlProps(dispatch)), React.useMemo(function () { return core.mapDispatchToMultiEnumProps(dispatch); }, [dispatch]))); };
var ctxToLabelProps = function (ctx, ownProps) {
    return core.mapStateToLabelProps({ jsonforms: __assign({}, ctx) }, ownProps);
};
var withJsonFormsContext = function (Component) {
    return function WithJsonFormsContext(props) {
        var ctx = useJsonForms();
        return React__default["default"].createElement(Component, { ctx: ctx, props: props });
    };
};
var withContextToJsonFormsRendererProps = function (Component) {
    return function WithContextToJsonFormsRendererProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var contextProps = ctxToJsonFormsRendererProps(ctx, props);
        return React__default["default"].createElement(Component, __assign({}, props, contextProps));
    };
};
var withContextToControlProps = function (Component) {
    return function WithContextToControlProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var controlProps = ctxToControlProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, controlProps, dispatchProps));
    };
};
var withContextToLayoutProps = function (Component) {
    return function WithContextToLayoutProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var layoutProps = ctxToLayoutProps(ctx, props);
        return React__default["default"].createElement(Component, __assign({}, props, layoutProps));
    };
};
var withContextToOneOfProps = function (Component) {
    return function WithContextToOneOfProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var oneOfProps = ctxToOneOfProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, oneOfProps, dispatchProps));
    };
};
var withContextToAnyOfProps = function (Component) {
    return function WithContextToAnyOfProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var oneOfProps = ctxToAnyOfProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, oneOfProps, dispatchProps));
    };
};
var withContextToAllOfProps = function (Component) {
    return function WithContextToAllOfProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var allOfProps = ctxToAllOfProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, allOfProps, dispatchProps));
    };
};
var withContextToDetailProps = function (Component) {
    return function WithContextToDetailProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var detailProps = ctxToControlWithDetailProps(ctx, props);
        return React__default["default"].createElement(Component, __assign({}, props, detailProps));
    };
};
var withContextToArrayLayoutProps = function (Component) {
    return function WithContextToArrayLayoutProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var arrayLayoutProps = ctxToArrayLayoutProps(ctx, props);
        var dispatchProps = ctxDispatchToArrayControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, arrayLayoutProps, dispatchProps));
    };
};
var withContextToArrayControlProps = function (Component) {
    return function WithContextToArrayControlProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToArrayControlProps(ctx, props);
        var dispatchProps = ctxDispatchToArrayControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, stateProps, dispatchProps));
    };
};
var withContextToMasterListItemProps = function (Component) {
    return function WithContextToMasterListItemProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToMasterListItemProps(ctx, props);
        return React__default["default"].createElement(Component, __assign({}, props, stateProps));
    };
};
var withContextToCellProps = function (Component) {
    return function WithContextToCellProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var cellProps = ctxToCellProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, cellProps));
    };
};
var withContextToDispatchCellProps = function (Component) {
    return function WithContextToDispatchCellProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var cellProps = ctxToDispatchCellProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, cellProps));
    };
};
var withContextToEnumCellProps = function (Component) {
    return function WithContextToEnumCellProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var cellProps = ctxToEnumCellProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, cellProps));
    };
};
var withContextToEnumProps = function (Component) {
    return function WithContextToEnumProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToEnumControlProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, stateProps));
    };
};
var withContextToOneOfEnumCellProps = function (Component) {
    return function WithContextToOneOfEnumCellProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var cellProps = ctxToOneOfEnumCellProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, cellProps));
    };
};
var withContextToOneOfEnumProps = function (Component) {
    return function WithContextToOneOfEnumProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToOneOfEnumControlProps(ctx, props);
        var dispatchProps = ctxDispatchToControlProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, stateProps));
    };
};
var withContextToMultiEnumProps = function (Component) {
    return function WithContextToMultiEnumProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToMultiEnumControlProps(ctx, props);
        var dispatchProps = ctxDispatchToMultiEnumProps(ctx.dispatch);
        return React__default["default"].createElement(Component, __assign({}, props, dispatchProps, stateProps));
    };
};
var withContextToLabelProps = function (Component) {
    return function WithContextToLabelProps(_a) {
        var ctx = _a.ctx, props = _a.props;
        var stateProps = ctxToLabelProps(ctx, props);
        return React__default["default"].createElement(Component, __assign({}, props, stateProps));
    };
};
var withJsonFormsRendererProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToJsonFormsRendererProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsControlProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToControlProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsLayoutProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToLayoutProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsOneOfProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToOneOfProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsAnyOfProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToAnyOfProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsAllOfProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToAllOfProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsDetailProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToDetailProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsArrayLayoutProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToArrayLayoutProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsArrayControlProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToArrayControlProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsMasterListItemProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToMasterListItemProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsCellProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToCellProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsDispatchCellProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToDispatchCellProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsEnumCellProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToEnumCellProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsEnumProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToEnumProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsOneOfEnumCellProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToOneOfEnumCellProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsOneOfEnumProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToOneOfEnumProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsMultiEnumProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToMultiEnumProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withJsonFormsLabelProps = function (Component, memoize) {
    if (memoize === void 0) { memoize = true; }
    return withJsonFormsContext(withContextToLabelProps(memoize ? React__default["default"].memo(Component) : Component));
};
var withTranslateProps = function (Component) {
    return function WithTranslateProps(props) {
        var _a, _b, _c, _d;
        var ctx = useJsonForms();
        var locale = (_b = (_a = ctx.i18n) === null || _a === void 0 ? void 0 : _a.locale) !== null && _b !== void 0 ? _b : core.defaultJsonFormsI18nState.locale;
        var t = (_d = (_c = ctx.i18n) === null || _c === void 0 ? void 0 : _c.translate) !== null && _d !== void 0 ? _d : core.defaultJsonFormsI18nState.translate;
        return React__default["default"].createElement(Component, __assign({}, props, { locale: locale, t: t }));
    };
};
var withArrayTranslationProps = function (Component) {
    return function withArrayTranslatationProps(props) {
        var translations = React.useMemo(function () {
            return core.getArrayTranslations(props.t, core.arrayDefaultTranslations, props.i18nKeyPrefix, props.label);
        }, [props.t, props.i18nKeyPrefix, props.label]);
        return React__default["default"].createElement(Component, __assign({}, props, { translations: translations }));
    };
};

var JsonFormsDispatchRenderer =  (function (_super) {
    __extends(JsonFormsDispatchRenderer, _super);
    function JsonFormsDispatchRenderer(props) {
        var _this = _super.call(this, props) || this;
        _this.state = {
            id: core.isControl(props.uischema)
                ? core.createId(props.uischema.scope)
                : undefined,
        };
        return _this;
    }
    JsonFormsDispatchRenderer.prototype.componentWillUnmount = function () {
        if (core.isControl(this.props.uischema)) {
            core.removeId(this.state.id);
        }
    };
    JsonFormsDispatchRenderer.prototype.componentDidUpdate = function (prevProps) {
        if (prevProps.schema !== this.props.schema) {
            core.removeId(this.state.id);
            this.setState({
                id: core.isControl(this.props.uischema)
                    ? core.createId(this.props.uischema.scope)
                    : undefined,
            });
        }
    };
    JsonFormsDispatchRenderer.prototype.render = function () {
        var _a = this.props, schema = _a.schema, rootSchema = _a.rootSchema, uischema = _a.uischema, path = _a.path, enabled = _a.enabled, renderers = _a.renderers, cells = _a.cells, config = _a.config;
        return (React__default["default"].createElement(TestAndRender, { uischema: uischema, schema: schema, rootSchema: rootSchema, path: path, enabled: enabled, renderers: renderers, cells: cells, id: this.state.id, config: config }));
    };
    return JsonFormsDispatchRenderer;
}(React__default["default"].Component));
var TestAndRender = React__default["default"].memo(function TestAndRender(props) {
    var testerContext = React.useMemo(function () { return ({
        rootSchema: props.rootSchema,
        config: props.config,
    }); }, [props.rootSchema, props.config]);
    var renderer = React.useMemo(function () {
        return maxBy__default["default"](props.renderers, function (r) {
            return r.tester(props.uischema, props.schema, testerContext);
        });
    }, [props.renderers, props.uischema, props.schema, testerContext]);
    if (renderer === undefined ||
        renderer.tester(props.uischema, props.schema, testerContext) === -1) {
        return React__default["default"].createElement(UnknownRenderer, { type: 'renderer' });
    }
    else {
        var Render = renderer.renderer;
        return (React__default["default"].createElement(Render, { uischema: props.uischema, schema: props.schema, path: props.path, enabled: props.enabled, renderers: props.renderers, cells: props.cells, id: props.id }));
    }
});
var ResolvedJsonFormsDispatchRenderer =  (function (_super) {
    __extends(ResolvedJsonFormsDispatchRenderer, _super);
    function ResolvedJsonFormsDispatchRenderer(props) {
        return _super.call(this, props) || this;
    }
    return ResolvedJsonFormsDispatchRenderer;
}(JsonFormsDispatchRenderer));
var JsonFormsDispatch = withJsonFormsRendererProps(JsonFormsDispatchRenderer);
var ResolvedJsonFormsDispatch = withJsonFormsRendererProps(ResolvedJsonFormsDispatchRenderer);
var JsonForms = function (props) {
    var ajv = props.ajv, data = props.data, schema = props.schema, uischema = props.uischema, renderers = props.renderers, cells = props.cells, onChange = props.onChange, config = props.config, uischemas = props.uischemas, readonly = props.readonly, validationMode = props.validationMode, i18n = props.i18n, additionalErrors = props.additionalErrors, middleware = props.middleware;
    var schemaToUse = React.useMemo(function () { return (schema !== undefined ? schema : core.Generate.jsonSchema(data)); }, [schema, data]);
    var uischemaToUse = React.useMemo(function () {
        return typeof uischema === 'object'
            ? uischema
            : core.Generate.uiSchema(schemaToUse, undefined, undefined, schemaToUse);
    }, [uischema, schemaToUse]);
    return (React__default["default"].createElement(JsonFormsStateProvider, { initState: {
            core: {
                ajv: ajv,
                data: data,
                schema: schemaToUse,
                uischema: uischemaToUse,
                validationMode: validationMode,
                additionalErrors: additionalErrors,
            },
            config: config,
            uischemas: uischemas,
            renderers: renderers,
            cells: cells,
            readonly: readonly,
            i18n: i18n,
        }, onChange: onChange, middleware: middleware },
        React__default["default"].createElement(JsonFormsDispatch, null)));
};

var Dispatch = function (_a) {
    var uischema = _a.uischema, schema = _a.schema, rootSchema = _a.rootSchema, path = _a.path, cells = _a.cells, id = _a.id, enabled = _a.enabled, renderers = _a.renderers, config = _a.config;
    var testerContext = React.useMemo(function () { return ({
        rootSchema: rootSchema,
        config: config,
    }); }, [rootSchema, config]);
    var cell = React.useMemo(function () { return maxBy__default["default"](cells, function (r) { return r.tester(uischema, schema, testerContext); }); }, [cells, uischema, schema, testerContext]);
    if (cell === undefined ||
        cell.tester(uischema, schema, testerContext) === -1) {
        return React__default["default"].createElement(UnknownRenderer, { type: 'cell' });
    }
    else {
        var Cell = cell.cell;
        return (React__default["default"].createElement(Cell, { uischema: uischema, schema: schema, enabled: enabled, path: path, id: id, renderers: renderers, cells: cells }));
    }
};
var DispatchCell = withJsonFormsDispatchCellProps(Dispatch);

exports.Control = Control;
exports.Dispatch = Dispatch;
exports.DispatchCell = DispatchCell;
exports.JsonForms = JsonForms;
exports.JsonFormsContext = JsonFormsContext;
exports.JsonFormsDispatch = JsonFormsDispatch;
exports.JsonFormsDispatchRenderer = JsonFormsDispatchRenderer;
exports.JsonFormsStateProvider = JsonFormsStateProvider;
exports.RendererComponent = RendererComponent;
exports.ResolvedJsonFormsDispatch = ResolvedJsonFormsDispatch;
exports.ResolvedJsonFormsDispatchRenderer = ResolvedJsonFormsDispatchRenderer;
exports.UnknownRenderer = UnknownRenderer;
exports.ctxDispatchToArrayControlProps = ctxDispatchToArrayControlProps;
exports.ctxDispatchToControlProps = ctxDispatchToControlProps;
exports.ctxDispatchToMultiEnumProps = ctxDispatchToMultiEnumProps;
exports.ctxToAllOfProps = ctxToAllOfProps;
exports.ctxToAnyOfProps = ctxToAnyOfProps;
exports.ctxToArrayControlProps = ctxToArrayControlProps;
exports.ctxToArrayLayoutProps = ctxToArrayLayoutProps;
exports.ctxToCellProps = ctxToCellProps;
exports.ctxToControlProps = ctxToControlProps;
exports.ctxToControlWithDetailProps = ctxToControlWithDetailProps;
exports.ctxToDispatchCellProps = ctxToDispatchCellProps;
exports.ctxToEnumCellProps = ctxToEnumCellProps;
exports.ctxToEnumControlProps = ctxToEnumControlProps;
exports.ctxToJsonFormsRendererProps = ctxToJsonFormsRendererProps;
exports.ctxToLabelProps = ctxToLabelProps;
exports.ctxToLayoutProps = ctxToLayoutProps;
exports.ctxToMasterListItemProps = ctxToMasterListItemProps;
exports.ctxToMultiEnumControlProps = ctxToMultiEnumControlProps;
exports.ctxToOneOfEnumCellProps = ctxToOneOfEnumCellProps;
exports.ctxToOneOfEnumControlProps = ctxToOneOfEnumControlProps;
exports.ctxToOneOfProps = ctxToOneOfProps;
exports.useJsonForms = useJsonForms;
exports.withArrayTranslationProps = withArrayTranslationProps;
exports.withContextToJsonFormsRendererProps = withContextToJsonFormsRendererProps;
exports.withJsonFormsAllOfProps = withJsonFormsAllOfProps;
exports.withJsonFormsAnyOfProps = withJsonFormsAnyOfProps;
exports.withJsonFormsArrayControlProps = withJsonFormsArrayControlProps;
exports.withJsonFormsArrayLayoutProps = withJsonFormsArrayLayoutProps;
exports.withJsonFormsCellProps = withJsonFormsCellProps;
exports.withJsonFormsContext = withJsonFormsContext;
exports.withJsonFormsControlProps = withJsonFormsControlProps;
exports.withJsonFormsDetailProps = withJsonFormsDetailProps;
exports.withJsonFormsDispatchCellProps = withJsonFormsDispatchCellProps;
exports.withJsonFormsEnumCellProps = withJsonFormsEnumCellProps;
exports.withJsonFormsEnumProps = withJsonFormsEnumProps;
exports.withJsonFormsLabelProps = withJsonFormsLabelProps;
exports.withJsonFormsLayoutProps = withJsonFormsLayoutProps;
exports.withJsonFormsMasterListItemProps = withJsonFormsMasterListItemProps;
exports.withJsonFormsMultiEnumProps = withJsonFormsMultiEnumProps;
exports.withJsonFormsOneOfEnumCellProps = withJsonFormsOneOfEnumCellProps;
exports.withJsonFormsOneOfEnumProps = withJsonFormsOneOfEnumProps;
exports.withJsonFormsOneOfProps = withJsonFormsOneOfProps;
exports.withJsonFormsRendererProps = withJsonFormsRendererProps;
exports.withTranslateProps = withTranslateProps;
//# sourceMappingURL=jsonforms-react.cjs.js.map
