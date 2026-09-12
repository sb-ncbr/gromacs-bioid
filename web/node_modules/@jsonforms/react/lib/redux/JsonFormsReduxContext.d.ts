import { JsonFormsSubStates } from '@jsonforms/core';
import { Reducer } from 'redux';
import React from 'react';
import { JsonFormsReduxContextProps } from '..';
export declare const JsonFormsReduxContext: import("react-redux").ConnectedComponent<({ children, dispatch, ...other }: JsonFormsReduxContextProps) => React.JSX.Element, import("react-redux").Omit<JsonFormsReduxContextProps, string | number>>;
export declare const jsonformsReducer: (additionalReducers?: {}) => Reducer<JsonFormsSubStates>;
