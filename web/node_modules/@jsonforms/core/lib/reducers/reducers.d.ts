import type { ControlElement, UISchemaElement } from '../models';
import type { JsonSchema } from '../models/jsonSchema';
import { JsonFormsUISchemaRegistryEntry } from '../store';
export declare const jsonFormsReducerConfig: {
    core: import("../store").Reducer<import("../store").JsonFormsCore, import("..").CoreActions>;
    renderers: import("../store").Reducer<import("../store").JsonFormsRendererRegistryEntry[], import("..").AddRendererAction | import("..").RemoveRendererAction>;
    cells: import("../store").Reducer<import("./cells").JsonFormsCellRendererRegistryState, import("..").AddCellRendererAction | import("..").RemoveCellRendererAction>;
    config: import("../store").Reducer<any, import("..").SetConfigAction>;
    uischemas: import("../store").Reducer<JsonFormsUISchemaRegistryEntry[], import("..").UISchemaActions>;
    defaultData: import("../store").Reducer<import("./default-data").JsonFormsDefaultDataRegistryEntry[], import("..").RegisterDefaultDataAction | import("..").UnregisterDefaultDataAction>;
    i18n: import("../store").Reducer<import("../store").JsonFormsI18nState, import("..").I18nActions>;
};
/**
 * Finds a registered UI schema to use, if any.
 * @param schema the JSON schema describing the data to be rendered
 * @param schemaPath the according schema path
 * @param path the instance path
 * @param fallback the type of the layout to use or a UI-schema-generator function
 * @param control may be checked for embedded inline uischema options
 */
export declare const findUISchema: (uischemas: JsonFormsUISchemaRegistryEntry[], schema: JsonSchema, schemaPath: string, path: string, fallback?: string | (() => UISchemaElement), control?: ControlElement, rootSchema?: JsonSchema) => UISchemaElement;
