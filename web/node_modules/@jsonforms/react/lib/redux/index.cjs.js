'use strict';

Object.defineProperty(exports, '__esModule', { value: true });

var core = require('@jsonforms/core');
var reactRedux = require('react-redux');
var redux = require('redux');
var React = require('react');
var react = require('@jsonforms/react');

function _interopDefaultLegacy (e) { return e && typeof e === 'object' && 'default' in e ? e : { 'default': e }; }

var React__default = /*#__PURE__*/_interopDefaultLegacy(React);

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

function __rest(s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
}

typeof SuppressedError === "function" ? SuppressedError : function (error, suppressed, message) {
    var e = new Error(message);
    return e.name = "SuppressedError", e.error = error, e.suppressed = suppressed, e;
};

var JsonFormsReduxProvider = function (_a) {
    var children = _a.children, dispatch = _a.dispatch, other = __rest(_a, ["children", "dispatch"]);
    return (React__default["default"].createElement(react.JsonFormsContext.Provider, { value: __assign({ dispatch: dispatch }, other) }, children));
};
var JsonFormsReduxContext = reactRedux.connect(function (state) { return (__assign({}, state.jsonforms)); })(JsonFormsReduxProvider);
var jsonformsReducer = function (additionalReducers) {
    if (additionalReducers === void 0) { additionalReducers = {}; }
    return redux.combineReducers(__assign({ core: core.coreReducer, renderers: core.rendererReducer, cells: core.cellReducer, config: core.configReducer, uischemas: core.uischemaRegistryReducer, i18n: core.i18nReducer }, additionalReducers));
};

exports.JsonFormsReduxContext = JsonFormsReduxContext;
exports.jsonformsReducer = jsonformsReducer;
//# sourceMappingURL=index.cjs.js.map
