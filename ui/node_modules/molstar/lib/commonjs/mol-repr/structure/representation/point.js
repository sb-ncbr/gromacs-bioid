"use strict";
/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.PointRepresentationProvider = exports.PointParams = void 0;
exports.getPointParams = getPointParams;
exports.PointRepresentation = PointRepresentation;
const element_point_1 = require("../visual/element-point");
const units_representation_1 = require("../units-representation");
const param_definition_1 = require("../../../mol-util/param-definition");
const representation_1 = require("../representation");
const representation_2 = require("../../../mol-repr/representation");
const base_1 = require("../../../mol-geo/geometry/base");
const PointVisuals = {
    'element-point': (ctx, getParams) => (0, units_representation_1.UnitsRepresentation)('Element points', ctx, getParams, element_point_1.ElementPointVisual),
    'structure-element-point': (ctx, getParams) => (0, representation_1.ComplexRepresentation)('Structure element points', ctx, getParams, element_point_1.StructureElementPointVisual),
};
exports.PointParams = {
    ...element_point_1.ElementPointParams,
    density: param_definition_1.ParamDefinition.Numeric(0.1, { min: 0, max: 1, step: 0.01 }, base_1.BaseGeometry.ShadingCategory),
    visuals: param_definition_1.ParamDefinition.MultiSelect(['element-point'], param_definition_1.ParamDefinition.objectToOptions(PointVisuals)),
};
function getPointParams(ctx, structure) {
    let params = exports.PointParams;
    if (structure.unitSymmetryGroups.length > 5000) {
        params = param_definition_1.ParamDefinition.clone(params);
        params.visuals.defaultValue = ['structure-element-point'];
    }
    return params;
}
function PointRepresentation(ctx, getParams) {
    return representation_2.Representation.createMulti('Point', ctx, getParams, representation_1.StructureRepresentationStateBuilder, PointVisuals);
}
exports.PointRepresentationProvider = (0, representation_1.StructureRepresentationProvider)({
    name: 'point',
    label: 'Point',
    description: 'Displays elements (atoms, coarse spheres) as points.',
    factory: PointRepresentation,
    getParams: getPointParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.PointParams),
    defaultColorTheme: { name: 'element-symbol' },
    defaultSizeTheme: { name: 'uniform' },
    isApplicable: (structure) => structure.elementCount > 0
});
