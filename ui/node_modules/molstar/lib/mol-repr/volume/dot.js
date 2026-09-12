/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { Grid, Volume } from '../../mol-model/volume';
import { Mesh } from '../../mol-geo/geometry/mesh/mesh';
import { VolumeVisual, VolumeRepresentation, VolumeRepresentationProvider } from './representation';
import { Representation } from '../representation';
import { EmptyLoci } from '../../mol-model/loci';
import { Interval } from '../../mol-data/int';
import { createVolumeCellLocationIterator, eachVolumeLoci } from './util';
import { BaseGeometry } from '../../mol-geo/geometry/base';
import { Spheres } from '../../mol-geo/geometry/spheres/spheres';
import { MeshBuilder } from '../../mol-geo/geometry/mesh/mesh-builder';
import { SpheresBuilder } from '../../mol-geo/geometry/spheres/spheres-builder';
import { Vec3 } from '../../mol-math/linear-algebra/3d/vec3';
import { addSphere } from '../../mol-geo/geometry/mesh/builder/sphere';
import { sphereVertexCount } from '../../mol-geo/primitive/sphere';
import { Points } from '../../mol-geo/geometry/points/points';
import { PointsBuilder } from '../../mol-geo/geometry/points/points-builder';
export const VolumeDotParams = {
    isoValue: Volume.IsoValueParam,
};
//
export const VolumeSphereParams = {
    ...Spheres.Params,
    ...Mesh.Params,
    ...VolumeDotParams,
    tryUseImpostor: PD.Boolean(true),
    detail: PD.Numeric(0, { min: 0, max: 3, step: 1 }, BaseGeometry.CustomQualityParamInfo),
};
export function VolumeSphereVisual(materialId, volume, key, props, webgl) {
    return props.tryUseImpostor && webgl && webgl.extensions.fragDepth && webgl.extensions.textureFloat
        ? VolumeSphereImpostorVisual(materialId)
        : VolumeSphereMeshVisual(materialId);
}
export function VolumeSphereImpostorVisual(materialId) {
    return VolumeVisual({
        defaultProps: PD.getDefaultValues(VolumeSphereParams),
        createGeometry: createVolumeSphereImpostor,
        createLocationIterator: createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats));
        },
        geometryUtils: Spheres.Utils,
        mustRecreate: (volumekey, props, webgl) => {
            return !props.tryUseImpostor || !webgl;
        }
    }, materialId);
}
export function VolumeSphereMeshVisual(materialId) {
    return VolumeVisual({
        defaultProps: PD.getDefaultValues(VolumeSphereParams),
        createGeometry: createVolumeSphereMesh,
        createLocationIterator: createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats) ||
                newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail);
        },
        geometryUtils: Mesh.Utils,
        mustRecreate: (volumekey, props, webgl) => {
            return props.tryUseImpostor && !!webgl;
        }
    }, materialId);
}
export function createVolumeSphereImpostor(ctx, volume, key, theme, props, spheres) {
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = Vec3();
    const [xn, yn, zn] = space.dimensions;
    const count = Math.ceil((xn * yn * zn) / 10);
    const builder = SpheresBuilder.create(count, Math.ceil(count / 2), spheres);
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                Vec3.set(p, x, y, z);
                Vec3.transformMat4(p, p, gridToCartn);
                builder.add(p[0], p[1], p[2], space.dataOffset(x, y, z));
            }
        }
    }
    const s = builder.getSpheres();
    s.setBoundingSphere(Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return s;
}
export function createVolumeSphereMesh(ctx, volume, key, theme, props, mesh) {
    const { detail, sizeFactor } = props;
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = Vec3();
    const [xn, yn, zn] = space.dimensions;
    const count = (xn * yn * zn) / 10;
    const vertexCount = count * sphereVertexCount(detail);
    const builderState = MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const l = Volume.Cell.Location(volume);
    const themeSize = theme.size.size;
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                Vec3.set(p, x, y, z);
                Vec3.transformMat4(p, p, gridToCartn);
                builderState.currentGroup = space.dataOffset(x, y, z);
                l.cell = builderState.currentGroup;
                const size = themeSize(l);
                addSphere(builderState, p, size * sizeFactor, detail);
            }
        }
    }
    const m = MeshBuilder.getMesh(builderState);
    m.setBoundingSphere(Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return m;
}
//
export const VolumePointParams = {
    ...Points.Params,
    ...VolumeDotParams,
};
export function VolumePointVisual(materialId) {
    return VolumeVisual({
        defaultProps: PD.getDefaultValues(VolumePointParams),
        createGeometry: createVolumePoint,
        createLocationIterator: createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats));
        },
        geometryUtils: Points.Utils,
    }, materialId);
}
export function createVolumePoint(ctx, volume, key, theme, props, points) {
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = Vec3();
    const [xn, yn, zn] = space.dimensions;
    const count = Math.ceil((xn * yn * zn) / 10);
    const builder = PointsBuilder.create(count, Math.ceil(count / 2), points);
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                Vec3.set(p, x, y, z);
                Vec3.transformMat4(p, p, gridToCartn);
                builder.add(p[0], p[1], p[2], space.dataOffset(x, y, z));
            }
        }
    }
    const pt = builder.getPoints();
    pt.setBoundingSphere(Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return pt;
}
//
function getLoci(volume, props) {
    return Volume.Isosurface.Loci(volume, props.isoValue);
}
function getDotLoci(pickingId, volume, key, props, id) {
    const { objectId, groupId } = pickingId;
    if (id === objectId) {
        const granularity = Volume.PickingGranularity.get(volume);
        if (granularity === 'volume') {
            return Volume.Loci(volume);
        }
        else if (granularity === 'object') {
            return Volume.Isosurface.Loci(volume, props.isoValue);
        }
        else {
            return Volume.Cell.Loci(volume, Interval.ofSingleton(groupId));
        }
    }
    return EmptyLoci;
}
function eachDot(loci, volume, key, props, apply) {
    return eachVolumeLoci(loci, volume, { isoValue: props.isoValue }, apply);
}
//
const DotVisuals = {
    'sphere': (ctx, getParams) => VolumeRepresentation('Dot sphere', ctx, getParams, VolumeSphereVisual, getLoci),
    'point': (ctx, getParams) => VolumeRepresentation('Dot point', ctx, getParams, VolumePointVisual, getLoci),
};
export const DotParams = {
    ...VolumeSphereParams,
    ...VolumePointParams,
    visuals: PD.MultiSelect(['sphere'], PD.objectToOptions(DotVisuals)),
    bumpFrequency: PD.Numeric(1, { min: 0, max: 10, step: 0.1 }, BaseGeometry.ShadingCategory),
};
export function getDotParams(ctx, volume) {
    const p = PD.clone(DotParams);
    p.isoValue = Volume.createIsoValueParam(Volume.IsoValue.relative(2), volume.grid.stats);
    return p;
}
export function DotRepresentation(ctx, getParams) {
    return Representation.createMulti('Dot', ctx, getParams, Representation.StateBuilder, DotVisuals);
}
export const DotRepresentationProvider = VolumeRepresentationProvider({
    name: 'dot',
    label: 'Dot',
    description: 'Displays dots of volumetric data.',
    factory: DotRepresentation,
    getParams: getDotParams,
    defaultValues: PD.getDefaultValues(DotParams),
    defaultColorTheme: { name: 'uniform' },
    defaultSizeTheme: { name: 'uniform' },
    isApplicable: (volume) => !Volume.isEmpty(volume) && !Volume.Segmentation.get(volume)
});
