"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlaneRepresentationProvider = exports.PlaneParams = void 0;
exports.getPlaneParams = getPlaneParams;
exports.PlaneRepresentation = PlaneRepresentation;
const param_definition_1 = require("../../../mol-util/param-definition");
const representation_1 = require("../representation");
const representation_2 = require("../../representation");
const plane_image_1 = require("../visual/plane-image");
const PlaneVisuals = {
    'plane-image': (ctx, getParams) => (0, representation_1.ComplexRepresentation)('Plane image', ctx, getParams, plane_image_1.PlaneImageVisual),
};
exports.PlaneParams = {
    ...plane_image_1.PlaneImageParams,
    visuals: param_definition_1.ParamDefinition.MultiSelect(['plane-image'], param_definition_1.ParamDefinition.objectToOptions(PlaneVisuals)),
};
function getPlaneParams(ctx, structure) {
    return exports.PlaneParams;
}
function PlaneRepresentation(ctx, getParams) {
    return representation_2.Representation.createMulti('Plane', ctx, getParams, representation_1.StructureRepresentationStateBuilder, PlaneVisuals);
}
exports.PlaneRepresentationProvider = (0, representation_1.StructureRepresentationProvider)({
    name: 'plane',
    label: 'Plane',
    description: 'Displays planes.',
    factory: PlaneRepresentation,
    getParams: getPlaneParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.PlaneParams),
    defaultColorTheme: { name: 'element-symbol' },
    defaultSizeTheme: { name: 'physical' },
    isApplicable: (structure) => structure.elementCount > 0,
    getData: (structure, props) => {
        return props.includeParent ? structure.asParent() : structure;
    },
    mustRecreate: (oldProps, newProps) => {
        return oldProps.includeParent !== newProps.includeParent;
    }
});
