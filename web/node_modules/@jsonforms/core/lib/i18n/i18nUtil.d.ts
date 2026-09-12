import type { ErrorObject } from 'ajv';
import { Labelable, UISchemaElement } from '../models';
import type { i18nJsonSchema, ErrorTranslator, Translator } from '../store';
import { ArrayDefaultTranslation, ArrayTranslations } from './arrayTranslations';
import { CombinatorDefaultTranslation, CombinatorTranslations } from './combinatorTranslations';
export declare const getI18nKeyPrefixBySchema: (schema: i18nJsonSchema | undefined, uischema: unknown | undefined) => string | undefined;
/**
 * Transforms a given path to a prefix which can be used for i18n keys.
 * Returns 'root' for empty paths and removes array indices
 */
export declare const transformPathToI18nPrefix: (path: string) => string;
export declare const getI18nKeyPrefix: (schema: i18nJsonSchema | undefined, uischema: unknown | undefined, path: string | undefined) => string;
export declare const getI18nKey: (schema: i18nJsonSchema | undefined, uischema: unknown | undefined, path: string | undefined, key: string) => string;
export declare const addI18nKeyToPrefix: (i18nKeyPrefix: string, key: string) => string;
export declare const defaultTranslator: Translator;
export declare const defaultErrorTranslator: ErrorTranslator;
/**
 * Returns the determined error message for the given errors.
 * All errors must correspond to the given schema, uischema or path.
 */
export declare const getCombinedErrorMessage: (errors: ErrorObject[], et: ErrorTranslator, t: Translator, schema?: i18nJsonSchema, uischema?: UISchemaElement, path?: string) => string;
/**
 * This can be used to internationalize the label of the given Labelable (e.g. UI Schema elements).
 * This should not be used for controls as there we have additional context in the form of the JSON Schema available.
 */
export declare const deriveLabelForUISchemaElement: (uischema: Labelable<boolean>, t: Translator) => string | undefined;
export declare const getArrayTranslations: (t: Translator, defaultTranslations: ArrayDefaultTranslation[], i18nKeyPrefix: string, label: string) => ArrayTranslations;
export declare const getCombinatorTranslations: (t: Translator, defaultTranslations: CombinatorDefaultTranslation[], i18nKeyPrefix: string, label: string) => CombinatorTranslations;
