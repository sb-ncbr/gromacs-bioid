import { AddRendererAction, RemoveRendererAction } from '../actions';
import { Reducer } from '../store/type';
import { JsonFormsRendererRegistryEntry } from '../store';
type ValidRendererReducerActions = AddRendererAction | RemoveRendererAction;
export declare const rendererReducer: Reducer<JsonFormsRendererRegistryEntry[], ValidRendererReducerActions>;
export {};
