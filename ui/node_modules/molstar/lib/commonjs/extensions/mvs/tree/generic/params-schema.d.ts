/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Field, OptionalField, RequiredField, ValueFor } from './field-schema';
type Fields = {
    [key in string]: Field;
};
/** Type of `ParamsSchema` where all fields are completely independent */
export interface SimpleParamsSchema<TFields extends Fields = Fields> {
    type: 'simple';
    /** Parameter fields */
    fields: TFields;
}
export declare function SimpleParamsSchema<TFields extends Fields>(fields: TFields): SimpleParamsSchema<TFields>;
type ValuesForFields<F extends Fields> = {
    [key in keyof F as (F[key] extends RequiredField<any> ? key : never)]: ValueFor<F[key]>;
} & {
    [key in keyof F as (F[key] extends OptionalField<any> ? key : never)]?: ValueFor<F[key]>;
};
type ValuesForSimpleParamsSchema<TSchema extends SimpleParamsSchema> = ValuesForFields<TSchema['fields']>;
type AllRequiredFields<F extends Fields> = {
    [key in keyof F]: F[key] extends Field<infer V> ? RequiredField<V> : never;
};
type AllRequiredSimple<TSchema extends SimpleParamsSchema> = SimpleParamsSchema<AllRequiredFields<TSchema['fields']>>;
type Cases = {
    [case_ in string]: SimpleParamsSchema;
};
/** Type of `ParamsSchema` where one field (discriminator) determines what other fields are allowed (i.e. discriminated union type) */
export interface UnionParamsSchema<TDiscriminator extends string = string, TCases extends Cases = Cases> {
    type: 'union';
    /** Name of parameter field that determines the rest (allowed values are defined by keys of `cases`) */
    discriminator: TDiscriminator;
    /** Description for the discriminator parameter field */
    discriminatorDescription: string;
    /** `ParamsSchema` for the rest, for each case of discriminator value */
    cases: TCases;
}
export declare function UnionParamsSchema<TDiscriminator extends string, TCases extends Cases>(discriminator: TDiscriminator, discriminatorDescription: string, cases: TCases): UnionParamsSchema<TDiscriminator, TCases>;
type ValuesForUnionParamsSchema<TSchema extends UnionParamsSchema, TCase extends keyof TSchema['cases'] = keyof TSchema['cases']> = TCase extends keyof TSchema['cases'] ? {
    [discriminator in TSchema['discriminator']]: TCase;
} & ValuesFor<TSchema['cases'][TCase]> : never;
type AllRequiredUnion<TSchema extends UnionParamsSchema> = UnionParamsSchema<TSchema['discriminator'], {
    [case_ in keyof TSchema['cases']]: AllRequired<TSchema['cases'][case_]>;
}>;
/** Schema for "params", i.e. a flat collection of key-value pairs */
export type ParamsSchema = SimpleParamsSchema | UnionParamsSchema;
/** Type of values for a params schema (optional fields can be missing) */
export type ValuesFor<P extends ParamsSchema> = P extends SimpleParamsSchema ? ValuesForSimpleParamsSchema<P> : P extends UnionParamsSchema ? ValuesForUnionParamsSchema<P> : never;
/** Variation of a params schema where all fields are required */
export type AllRequired<P extends ParamsSchema> = P extends SimpleParamsSchema ? AllRequiredSimple<P> : P extends UnionParamsSchema ? AllRequiredUnion<P> : never;
declare function AllRequiredSimple<TSchema extends SimpleParamsSchema>(schema: TSchema): AllRequired<TSchema>;
declare function AllRequiredUnion<TSchema extends UnionParamsSchema>(schema: TSchema): AllRequired<TSchema>;
export declare function AllRequired<TSchema extends ParamsSchema>(schema: TSchema): AllRequired<TSchema>;
/** Type of full values for a params schema, i.e. including all optional fields */
export type FullValuesFor<P extends ParamsSchema> = ValuesFor<AllRequired<P>>;
interface ValidationOptions {
    /** Check that all parameters (including optional) have a value provided. */
    requireAll?: boolean;
    /** Check there are extra parameters other that those defined in the schema. */
    noExtra?: boolean;
}
/** Return `undefined` if `values` contains correct value types for `schema`,
 * return description of validation issues, if `values` have wrong type.
 * If `options.requireAll`, all parameters (including optional) must have a value provided.
 * If `options.noExtra` is true, presence of any extra parameters is treated as an issue. */
export declare function paramsValidationIssues<P extends ParamsSchema>(schema: P, values: {
    [k: string]: any;
}, options?: ValidationOptions): string[] | undefined;
/** Add default parameter values to `values` based on a parameter schema (only for optional parameters) */
export declare function addParamDefaults<P extends ParamsSchema>(schema: P, values: ValuesFor<P>): FullValuesFor<P>;
export {};
