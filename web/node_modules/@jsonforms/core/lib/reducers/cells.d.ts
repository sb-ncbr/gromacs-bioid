import { AddCellRendererAction, RemoveCellRendererAction } from '../actions';
import { JsonFormsCellRendererRegistryEntry, Reducer } from '../store';
type ValidCellReducerActions = AddCellRendererAction | RemoveCellRendererAction;
export type JsonFormsCellRendererRegistryState = JsonFormsCellRendererRegistryEntry[];
export declare const cellReducer: Reducer<JsonFormsCellRendererRegistryState, ValidCellReducerActions>;
export {};
