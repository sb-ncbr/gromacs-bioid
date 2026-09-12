import { UISchemaActions } from '../actions';
import type { JsonSchema, UISchemaElement } from '../models';
import type { Reducer } from '../store/type';
import { JsonFormsUISchemaRegistryEntry } from '../store';
export declare const uischemaRegistryReducer: Reducer<JsonFormsUISchemaRegistryEntry[], UISchemaActions>;
export declare const findMatchingUISchema: (state: JsonFormsUISchemaRegistryEntry[]) => (jsonSchema: JsonSchema, schemaPath: string, path: string) => UISchemaElement;
