import type { JsonSchema } from '../models';
export declare const getFirstPrimitiveProp: (schema: unknown) => string;
/**
 * Tests whether the schema has an enum based on oneOf.
 */
export declare const isOneOfEnumSchema: (schema: JsonSchema) => boolean;
/**
 * Tests whether the schema has an enum.
 */
export declare const isEnumSchema: (schema: JsonSchema) => any;
