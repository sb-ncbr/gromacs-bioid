"use strict";
/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SimpleParamsSchema = SimpleParamsSchema;
exports.UnionParamsSchema = UnionParamsSchema;
exports.AllRequired = AllRequired;
exports.paramsValidationIssues = paramsValidationIssues;
exports.addParamDefaults = addParamDefaults;
const object_1 = require("../../../../mol-util/object");
const field_schema_1 = require("./field-schema");
function SimpleParamsSchema(fields) {
    return { type: 'simple', fields };
}
function UnionParamsSchema(discriminator, discriminatorDescription, cases) {
    return { type: 'union', discriminator, discriminatorDescription, cases };
}
function AllRequiredSimple(schema) {
    const newFields = (0, object_1.mapObjectMap)(schema.fields, field => (0, field_schema_1.RequiredField)(field.type, field.description));
    return SimpleParamsSchema(newFields);
}
function AllRequiredUnion(schema) {
    const newCases = (0, object_1.mapObjectMap)(schema.cases, AllRequired);
    return UnionParamsSchema(schema.discriminator, schema.discriminatorDescription, newCases);
}
function AllRequired(schema) {
    if (schema.type === 'simple') {
        return AllRequiredSimple(schema);
    }
    else {
        return AllRequiredUnion(schema);
    }
}
/** Return `undefined` if `values` contains correct value types for `schema`,
 * return description of validation issues, if `values` have wrong type.
 * If `options.requireAll`, all parameters (including optional) must have a value provided.
 * If `options.noExtra` is true, presence of any extra parameters is treated as an issue. */
function paramsValidationIssues(schema, values, options = {}) {
    if (!(0, object_1.isPlainObject)(values))
        return [`Parameters must be an object, not ${values}`];
    if (schema.type === 'simple') {
        return simpleParamsValidationIssue(schema, values, options);
    }
    else {
        return unionParamsValidationIssues(schema, values, options);
    }
}
function simpleParamsValidationIssue(schema, values, options) {
    for (const key in schema.fields) {
        const fieldSchema = schema.fields[key];
        if (Object.hasOwn(values, key)) {
            const value = values[key];
            const issues = (0, field_schema_1.fieldValidationIssues)(fieldSchema, value);
            if (issues)
                return [`Invalid value for parameter "${key}":`, ...issues.map(s => '  ' + s)];
        }
        else {
            if (fieldSchema.required)
                return [`Missing required parameter "${key}".`];
            if (options.requireAll)
                return [`Missing optional parameter "${key}".`];
        }
    }
    if (options.noExtra) {
        for (const key in values) {
            if (!Object.hasOwn(schema.fields, key))
                return [`Unknown parameter "${key}".`];
        }
    }
    return undefined;
}
function unionParamsValidationIssues(schema, values, options) {
    if (!Object.hasOwn(values, schema.discriminator)) {
        return [`Missing required parameter "${schema.discriminator}".`];
    }
    const case_ = values[schema.discriminator];
    const subschema = schema.cases[case_];
    if (subschema === undefined) {
        const allowedCases = Object.keys(schema.cases).map(x => `"${x}"`).join(' | ');
        return [
            `Invalid value for parameter "${schema.discriminator}":`,
            `"${case_}" is not a valid value for literal type (${allowedCases})`,
        ];
    }
    const issues = paramsValidationIssues(subschema, (0, object_1.omitObjectKeys)(values, [schema.discriminator]), options);
    if (issues) {
        issues.unshift(`(case "${schema.discriminator}": "${case_}")`);
        return issues.map(s => '  ' + s);
    }
    return undefined;
}
/** Add default parameter values to `values` based on a parameter schema (only for optional parameters) */
function addParamDefaults(schema, values) {
    if (schema.type === 'simple') {
        return addSimpleParamsDefaults(schema, values);
    }
    else {
        return addUnionParamsDefaults(schema, values);
    }
}
function addSimpleParamsDefaults(schema, values) {
    const out = { ...values };
    for (const key in schema.fields) {
        const field = schema.fields[key];
        if (!field.required && out[key] === undefined) {
            out[key] = field.default;
        }
    }
    return out;
}
function addUnionParamsDefaults(schema, values) {
    const case_ = values[schema.discriminator];
    const subschema = schema.cases[case_];
    return addParamDefaults(subschema, values);
}
