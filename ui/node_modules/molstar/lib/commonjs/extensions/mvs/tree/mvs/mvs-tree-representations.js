"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.MVSVolumeRepresentationParams = exports.MVSRepresentationParams = void 0;
const field_schema_1 = require("../generic/field-schema");
const params_schema_1 = require("../generic/params-schema");
const Cartoon = {
    /** Scales the corresponding visuals */
    size_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Scales the corresponding visuals.'),
    /** Simplify corkscrew helices to tubes. */
    tubular_helices: (0, field_schema_1.OptionalField)(field_schema_1.bool, false, 'Simplify corkscrew helices to tubes.'),
};
const BallAndStick = {
    /** Scales the corresponding visuals */
    size_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Scales the corresponding visuals.'),
    /** Controls whether hydrogen atoms are drawn. */
    ignore_hydrogens: (0, field_schema_1.OptionalField)(field_schema_1.bool, false, 'Controls whether hydrogen atoms are drawn.'),
};
const Spacefill = {
    /** Scales the corresponding visuals */
    size_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Scales the corresponding visuals.'),
    /** Controls whether hydrogen atoms are drawn. */
    ignore_hydrogens: (0, field_schema_1.OptionalField)(field_schema_1.bool, false, 'Controls whether hydrogen atoms are drawn.'),
};
const Carbohydrate = {
    /** Scales the corresponding visuals */
    size_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Scales the corresponding visuals.'),
};
const Surface = {
    /** Scales the corresponding visuals */
    size_factor: (0, field_schema_1.OptionalField)(field_schema_1.float, 1, 'Scales the corresponding visuals.'),
    /** Controls whether hydrogen atoms are drawn. */
    ignore_hydrogens: (0, field_schema_1.OptionalField)(field_schema_1.bool, false, 'Controls whether hydrogen atoms are drawn.'),
};
exports.MVSRepresentationParams = (0, params_schema_1.UnionParamsSchema)('type', 'Representation type', {
    cartoon: (0, params_schema_1.SimpleParamsSchema)(Cartoon),
    ball_and_stick: (0, params_schema_1.SimpleParamsSchema)(BallAndStick),
    spacefill: (0, params_schema_1.SimpleParamsSchema)(Spacefill),
    carbohydrate: (0, params_schema_1.SimpleParamsSchema)(Carbohydrate),
    surface: (0, params_schema_1.SimpleParamsSchema)(Surface),
});
const VolumeIsoSurface = {
    /** Relative isovalue. */
    relative_isovalue: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.float), null, 'Relative isovalue.'),
    /** Absolute isovalue. Overrides `relative_isovalue`. */
    absolute_isovalue: (0, field_schema_1.OptionalField)((0, field_schema_1.nullable)(field_schema_1.float), null, 'Absolute isovalue. Overrides `relative_isovalue`.'),
    /** Show mesh wireframe. Defaults to false. */
    show_wireframe: (0, field_schema_1.OptionalField)(field_schema_1.bool, false, 'Show mesh wireframe. Defaults to false.'),
    /** Show mesh faces. Defaults to true. */
    show_faces: (0, field_schema_1.OptionalField)(field_schema_1.bool, true, 'Show mesh faces. Defaults to true.'),
};
exports.MVSVolumeRepresentationParams = (0, params_schema_1.UnionParamsSchema)('type', 'Representation type', {
    'isosurface': (0, params_schema_1.SimpleParamsSchema)(VolumeIsoSurface),
});
