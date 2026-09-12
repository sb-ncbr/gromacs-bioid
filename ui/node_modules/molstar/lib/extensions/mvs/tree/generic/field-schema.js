/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import * as iots from 'io-ts';
import { PathReporter } from 'io-ts/PathReporter';
import { onelinerJsonString } from '../../../../mol-util/json';
/** Type definition for a string  */
export const str = iots.string;
/** Type definition for an integer  */
export const int = iots.Integer;
/** Type definition for a float or integer number  */
export const float = iots.number;
/** Type definition for a boolean  */
export const bool = iots.boolean;
/** Type definition for a tuple, e.g. `tuple([str, int, int])`  */
export const tuple = iots.tuple;
/** Type definition for a list/array, e.g. `list(str)`  */
export const list = iots.array;
/** Type definition for union types, e.g. `union([str, int])` means string or integer  */
export const union = iots.union;
/** Type definition used to create objects */
export const obj = iots.type;
/** Type definition used to create partial objects */
export const partial = iots.partial;
/** Type definition for nullable types, e.g. `nullable(str)` means string or `null`  */
export function nullable(type) {
    return union([type, iots.null]);
}
/** Type definition for literal types, e.g. `literal('red', 'green', 'blue')` means 'red' or 'green' or 'blue'  */
export function literal(...values) {
    if (values.length === 0) {
        throw new Error(`literal type must have at least one value`);
    }
    const typeName = `(${values.map(v => onelinerJsonString(v)).join(' | ')})`;
    return new iots.Type(typeName, ((value) => values.includes(value)), (value, ctx) => values.includes(value) ? { _tag: 'Right', right: value } : { _tag: 'Left', left: [{ value: value, context: ctx, message: `"${value}" is not a valid value for literal type ${typeName}` }] }, value => value);
}
/** Type definition for mapping between two types, e.g. `mapping(str, float)` means type `{ [key in string]: number }` */
export function mapping(from, to) {
    return iots.record(from, to);
}
export function RequiredField(type, description) {
    return { type, required: true, description };
}
export function OptionalField(type, defaultValue, description) {
    return { type, required: false, description, default: defaultValue };
}
/** Return `undefined` if `value` has correct type for `field`, regardsless of if required or optional.
 * Return description of validation issues, if `value` has wrong type. */
export function fieldValidationIssues(field, value) {
    const validation = field.type.decode(value);
    if (validation._tag === 'Right') {
        return undefined;
    }
    else {
        return PathReporter.report(validation);
    }
}
