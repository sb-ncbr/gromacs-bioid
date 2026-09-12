/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { ComplexRepresentation, StructureRepresentationProvider, StructureRepresentationStateBuilder } from '../representation';
import { Representation } from '../../representation';
import { PlaneImageParams, PlaneImageVisual } from '../visual/plane-image';
const PlaneVisuals = {
    'plane-image': (ctx, getParams) => ComplexRepresentation('Plane image', ctx, getParams, PlaneImageVisual),
};
export const PlaneParams = {
    ...PlaneImageParams,
    visuals: PD.MultiSelect(['plane-image'], PD.objectToOptions(PlaneVisuals)),
};
export function getPlaneParams(ctx, structure) {
    return PlaneParams;
}
export function PlaneRepresentation(ctx, getParams) {
    return Representation.createMulti('Plane', ctx, getParams, StructureRepresentationStateBuilder, PlaneVisuals);
}
export const PlaneRepresentationProvider = StructureRepresentationProvider({
    name: 'plane',
    label: 'Plane',
    description: 'Displays planes.',
    factory: PlaneRepresentation,
    getParams: getPlaneParams,
    defaultValues: PD.getDefaultValues(PlaneParams),
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
