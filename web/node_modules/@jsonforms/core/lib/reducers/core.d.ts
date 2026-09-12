import { CoreActions, InitAction, UpdateCoreAction } from '../actions';
import { JsonFormsCore, Reducer, ValidationMode } from '../store';
import type Ajv from 'ajv';
import type { ErrorObject } from 'ajv';
export declare const initState: JsonFormsCore;
export declare const getValidationMode: (state: JsonFormsCore, action?: InitAction | UpdateCoreAction) => ValidationMode;
export declare const getAdditionalErrors: (state: JsonFormsCore, action?: InitAction | UpdateCoreAction) => ErrorObject[];
export declare const getOrCreateAjv: (state: JsonFormsCore, action?: InitAction | UpdateCoreAction) => Ajv;
export declare const coreReducer: Reducer<JsonFormsCore, CoreActions>;
