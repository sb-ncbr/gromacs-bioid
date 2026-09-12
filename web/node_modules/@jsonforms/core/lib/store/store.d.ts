import type { Store } from './type';
import { RankedTester, UISchemaTester } from '../testers';
import { JsonSchema, UISchemaElement } from '../models';
import type Ajv from 'ajv';
import type { ErrorObject, ValidateFunction } from 'ajv';
import { JsonFormsI18nState } from './i18nTypes';
/**
 * JSONForms store.
 */
export interface JsonFormsStore extends Store<JsonFormsState> {
}
/**
 * The state shape of JSONForms.
 */
export interface JsonFormsState {
    /**
     * Represents JSONForm's sub-state.
     */
    jsonforms: JsonFormsSubStates;
}
export interface JsonFormsSubStates {
    /**
     * Substate for storing mandatory sub-state.
     */
    core?: JsonFormsCore;
    /**
     * Global configuration options.
     */
    config?: any;
    /**
     * All available renderers.
     */
    renderers?: JsonFormsRendererRegistryEntry[];
    /**
     * All available cell renderers.
     */
    cells?: JsonFormsCellRendererRegistryEntry[];
    /**
     * I18n settings.
     */
    i18n?: JsonFormsI18nState;
    /**
     * The UI schema registry used in detail renderers.
     */
    uischemas?: JsonFormsUISchemaRegistryEntry[];
    /**
     * If true, sets all controls to read-only.
     */
    readonly?: boolean;
    [additionalState: string]: any;
}
export type ValidationMode = 'ValidateAndShow' | 'ValidateAndHide' | 'NoValidation';
export interface JsonFormsCore {
    data: any;
    schema: JsonSchema;
    uischema: UISchemaElement;
    errors?: ErrorObject[];
    additionalErrors?: ErrorObject[];
    validator?: ValidateFunction;
    ajv?: Ajv;
    validationMode?: ValidationMode;
}
export interface JsonFormsRendererRegistryEntry {
    tester: RankedTester;
    renderer: any;
}
export interface JsonFormsUISchemaRegistryEntry {
    tester: UISchemaTester;
    uischema: UISchemaElement;
}
export interface JsonFormsCellRendererRegistryEntry {
    tester: RankedTester;
    cell: any;
}
export interface JsonFormsExtendedState<T> extends JsonFormsState {
    jsonforms: {
        [subState: string]: T;
    };
}
