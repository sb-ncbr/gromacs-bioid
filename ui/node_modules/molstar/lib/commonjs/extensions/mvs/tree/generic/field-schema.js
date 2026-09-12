"use strict";
/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.partial = exports.obj = exports.union = exports.list = exports.tuple = exports.bool = exports.float = exports.int = exports.str = void 0;
exports.nullable = nullable;
exports.literal = literal;
exports.mapping = mapping;
exports.RequiredField = RequiredField;
exports.OptionalField = OptionalField;
exports.fieldValidationIssues = fieldValidationIssues;
const tslib_1 = require("tslib");
const iots = tslib_1.__importStar(require("io-ts"));
const PathReporter_1 = require("io-ts/PathReporter");
const json_1 = require("../../../../mol-util/json");
/** Type definition for a string  */
exports.str = iots.string;
/** Type definition for an integer  */
exports.int = iots.Integer;
/** Type definition for a float or integer number  */
exports.float = iots.number;
/** Type definition for a boolean  */
exports.bool = iots.boolean;
/** Type definition for a tuple, e.g. `tuple([str, int, int])`  */
exports.tuple = iots.tuple;
/** Type definition for a list/array, e.g. `list(str)`  */
exports.list = iots.array;
/** Type definition for union types, e.g. `union([str, int])` means string or integer  */
exports.union = iots.union;
/** Type definition used to create objects */
exports.obj = iots.type;
/** Type definition used to create partial objects */
exports.partial = iots.partial;
/** Type definition for nullable types, e.g. `nullable(str)` means string or `null`  */
function nullable(type) {
    return (0, exports.union)([type, iots.null]);
}
/** Type definition for literal types, e.g. `literal('red', 'green', 'blue')` means 'red' or 'green' or 'blue'  */
function literal(...values) {
    if (values.length === 0) {
        throw new Error(`literal type must have at least one value`);
    }
    const typeName = `(${values.map(v => (0, json_1.onelinerJsonString)(v)).join(' | ')})`;
    return new iots.Type(typeName, ((value) => values.includes(value)), (value, ctx) => values.includes(value) ? { _tag: 'Right', right: value } : { _tag: 'Left', left: [{ value: value, context: ctx, message: `"${value}" is not a valid value for literal type ${typeName}` }] }, value => value);
}
/** Type definition for mapping between two types, e.g. `mapping(str, float)` means type `{ [key in string]: number }` */
function mapping(from, to) {
    return iots.record(from, to);
}
function RequiredField(type, description) {
    return { type, required: true, description };
}
function OptionalField(type, defaultValue, description) {
    return { type, required: false, description, default: defaultValue };
}
/** Return `undefined` if `value` has correct type for `field`, regardsless of if required or optional.
 * Return description of validation issues, if `value` has wrong type. */
function fieldValidationIssues(field, value) {
    const validation = field.type.decode(value);
    if (validation._tag === 'Right') {
        return undefined;
    }
    else {
        return PathReporter_1.PathReporter.report(validation);
    }
}
