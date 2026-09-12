/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import * as iots from 'io-ts';
/** All types that can be used in tree node params.
 * Can be extended, this is just to list them all in one place and possibly catch some typing errors */
type AllowedValueTypes = string | number | boolean | null | [number, number, number] | string[] | number[] | {};
/** Type definition for a string  */
export declare const str: iots.StringC;
/** Type definition for an integer  */
export declare const int: iots.RefinementC<iots.NumberC, number>;
/** Type definition for a float or integer number  */
export declare const float: iots.NumberC;
/** Type definition for a boolean  */
export declare const bool: iots.BooleanC;
/** Type definition for a tuple, e.g. `tuple([str, int, int])`  */
export declare const tuple: typeof iots.tuple;
/** Type definition for a list/array, e.g. `list(str)`  */
export declare const list: typeof iots.array;
/** Type definition for union types, e.g. `union([str, int])` means string or integer  */
export declare const union: typeof iots.union;
/** Type definition used to create objects */
export declare const obj: typeof iots.type;
/** Type definition used to create partial objects */
export declare const partial: typeof iots.partial;
/** Type definition for nullable types, e.g. `nullable(str)` means string or `null`  */
export declare function nullable<T extends iots.Type<any>>(type: T): iots.UnionC<[T, iots.NullC]>;
/** Type definition for literal types, e.g. `literal('red', 'green', 'blue')` means 'red' or 'green' or 'blue'  */
export declare function literal<V extends string | number | boolean>(...values: V[]): iots.Type<V, V, unknown>;
/** Type definition for mapping between two types, e.g. `mapping(str, float)` means type `{ [key in string]: number }` */
export declare function mapping<A extends iots.Type<any>, B extends iots.Type<any>>(from: A, to: B): iots.RecordC<A, B>;
interface FieldBase<V extends AllowedValueTypes = any, R extends boolean = boolean> {
    /** Definition of allowed types for the field */
    type: iots.Type<V>;
    /** If `required===true`, the value must always be defined in molviewspec format (can be `null` if `type` allows it).
     * If `required===false`, the value can be ommitted (meaning that a default should be used).
     * If `type` allows `null`, the default must be `null`. */
    required: R;
    /** Description of what the field value means */
    description: string;
}
/** Schema for param field which must always be provided (has no default value) */
export interface RequiredField<V extends AllowedValueTypes = any> extends FieldBase<V> {
    required: true;
}
export declare function RequiredField<V extends AllowedValueTypes>(type: iots.Type<V>, description: string): RequiredField<V>;
/** Schema for param field which can be dropped (meaning that a default value will be used) */
export interface OptionalField<V extends AllowedValueTypes = any> extends FieldBase<V> {
    required: false;
    /** Default value for optional field.
     * If field type allows `null`, default must be `null` (this is to avoid issues in languages that do not distinguish `null` and `undefined`). */
    default: DefaultValue<V>;
}
export declare function OptionalField<V extends AllowedValueTypes>(type: iots.Type<V>, defaultValue: DefaultValue<V>, description: string): OptionalField<V>;
/** Schema for one field in params (i.e. a value in a top-level key-value pair) */
export type Field<V extends AllowedValueTypes = any> = RequiredField<V> | OptionalField<V>;
/** Type of valid default value for value type `V` (if the type allows `null`, the default must be `null`) */
type DefaultValue<V extends AllowedValueTypes> = null extends V ? null : V;
/** Type of valid value for field of type `F` (never includes `undefined`, even if field is optional) */
export type ValueFor<F extends Field | iots.Any> = F extends Field<infer V> ? V : F extends iots.Any ? iots.TypeOf<F> : never;
/** Return `undefined` if `value` has correct type for `field`, regardsless of if required or optional.
 * Return description of validation issues, if `value` has wrong type. */
export declare function fieldValidationIssues<F extends Field>(field: F, value: any): string[] | undefined;
export {};
