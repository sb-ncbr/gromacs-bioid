import { CoreActions } from '../actions';
import { JsonFormsCore } from '../store';
export interface Middleware {
    (state: JsonFormsCore, action: CoreActions, defaultReducer: (state: JsonFormsCore, action: CoreActions) => JsonFormsCore): JsonFormsCore;
}
export declare const defaultMiddleware: Middleware;
