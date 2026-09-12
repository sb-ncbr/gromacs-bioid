/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ElementPointVisual, ElementPointParams, StructureElementPointVisual } from '../visual/element-point';
import { UnitsRepresentation } from '../units-representation';
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { ComplexRepresentation, StructureRepresentationProvider, StructureRepresentationStateBuilder } from '../representation';
import { Representation } from '../../../mol-repr/representation';
import { BaseGeometry } from '../../../mol-geo/geometry/base';
const PointVisuals = {
    'element-point': (ctx, getParams) => UnitsRepresentation('Element points', ctx, getParams, ElementPointVisual),
    'structure-element-point': (ctx, getParams) => ComplexRepresentation('Structure element points', ctx, getParams, StructureElementPointVisual),
};
export const PointParams = {
    ...ElementPointParams,
    density: PD.Numeric(0.1, { min: 0, max: 1, step: 0.01 }, BaseGeometry.ShadingCategory),
    visuals: PD.MultiSelect(['element-point'], PD.objectToOptions(PointVisuals)),
};
export function getPointParams(ctx, structure) {
    let params = PointParams;
    if (structure.unitSymmetryGroups.length > 5000) {
        params = PD.clone(params);
        params.visuals.defaultValue = ['structure-element-point'];
    }
    return params;
}
export function PointRepresentation(ctx, getParams) {
    return Representation.createMulti('Point', ctx, getParams, StructureRepresentationStateBuilder, PointVisuals);
}
export const PointRepresentationProvider = StructureRepresentationProvider({
    name: 'point',
    label: 'Point',
    description: 'Displays elements (atoms, coarse spheres) as points.',
    factory: PointRepresentation,
    getParams: getPointParams,
    defaultValues: PD.getDefaultValues(PointParams),
    defaultColorTheme: { name: 'element-symbol' },
    defaultSizeTheme: { name: 'uniform' },
    isApplicable: (structure) => structure.elementCount > 0
});
