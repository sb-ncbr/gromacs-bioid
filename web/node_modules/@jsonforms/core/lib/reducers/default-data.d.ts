import { RegisterDefaultDataAction, UnregisterDefaultDataAction } from '../actions';
import type { Reducer } from '../store/type';
import { JsonFormsState } from '../store';
export interface JsonFormsDefaultDataRegistryEntry {
    schemaPath: string;
    data: any;
}
type ValidDefaultDataActions = RegisterDefaultDataAction | UnregisterDefaultDataAction;
export declare const defaultDataReducer: Reducer<JsonFormsDefaultDataRegistryEntry[], ValidDefaultDataActions>;
export declare const getDefaultData: (state: JsonFormsState) => JsonFormsDefaultDataRegistryEntry[];
export declare const extractDefaultData: (state: JsonFormsDefaultDataRegistryEntry[]) => JsonFormsDefaultDataRegistryEntry[];
export {};
