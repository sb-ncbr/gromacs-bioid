import { coreReducer, rendererReducer, cellReducer, configReducer, uischemaRegistryReducer, i18nReducer } from '@jsonforms/core';
import { connect } from 'react-redux';
import { combineReducers } from 'redux';
import React from 'react';
import { JsonFormsContext } from '@jsonforms/react';

const JsonFormsReduxProvider = ({ children, dispatch, ...other }) => {
    return (React.createElement(JsonFormsContext.Provider, { value: {
            dispatch,
            ...other,
        } }, children));
};
const JsonFormsReduxContext = connect((state) => ({
    ...state.jsonforms,
}))(JsonFormsReduxProvider);
const jsonformsReducer = (additionalReducers = {}) => combineReducers({
    core: coreReducer,
    renderers: rendererReducer,
    cells: cellReducer,
    config: configReducer,
    uischemas: uischemaRegistryReducer,
    i18n: i18nReducer,
    ...additionalReducers,
});

export { JsonFormsReduxContext, jsonformsReducer };
//# sourceMappingURL=index.js.map
