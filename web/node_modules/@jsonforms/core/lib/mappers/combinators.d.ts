import type { ControlElement, JsonSchema, UISchemaElement } from '../models';
import { JsonFormsUISchemaRegistryEntry } from '../store';
export interface CombinatorSubSchemaRenderInfo {
    schema: JsonSchema;
    uischema: UISchemaElement;
    label: string;
}
export type CombinatorKeyword = 'anyOf' | 'oneOf' | 'allOf';
export declare const createCombinatorRenderInfos: (combinatorSubSchemas: JsonSchema[], rootSchema: JsonSchema, keyword: CombinatorKeyword, control: ControlElement, path: string, uischemas: JsonFormsUISchemaRegistryEntry[]) => CombinatorSubSchemaRenderInfo[];
