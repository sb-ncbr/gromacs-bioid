"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.DotRepresentationProvider = exports.DotParams = exports.VolumePointParams = exports.VolumeSphereParams = exports.VolumeDotParams = void 0;
exports.VolumeSphereVisual = VolumeSphereVisual;
exports.VolumeSphereImpostorVisual = VolumeSphereImpostorVisual;
exports.VolumeSphereMeshVisual = VolumeSphereMeshVisual;
exports.createVolumeSphereImpostor = createVolumeSphereImpostor;
exports.createVolumeSphereMesh = createVolumeSphereMesh;
exports.VolumePointVisual = VolumePointVisual;
exports.createVolumePoint = createVolumePoint;
exports.getDotParams = getDotParams;
exports.DotRepresentation = DotRepresentation;
const param_definition_1 = require("../../mol-util/param-definition");
const volume_1 = require("../../mol-model/volume");
const mesh_1 = require("../../mol-geo/geometry/mesh/mesh");
const representation_1 = require("./representation");
const representation_2 = require("../representation");
const loci_1 = require("../../mol-model/loci");
const int_1 = require("../../mol-data/int");
const util_1 = require("./util");
const base_1 = require("../../mol-geo/geometry/base");
const spheres_1 = require("../../mol-geo/geometry/spheres/spheres");
const mesh_builder_1 = require("../../mol-geo/geometry/mesh/mesh-builder");
const spheres_builder_1 = require("../../mol-geo/geometry/spheres/spheres-builder");
const vec3_1 = require("../../mol-math/linear-algebra/3d/vec3");
const sphere_1 = require("../../mol-geo/geometry/mesh/builder/sphere");
const sphere_2 = require("../../mol-geo/primitive/sphere");
const points_1 = require("../../mol-geo/geometry/points/points");
const points_builder_1 = require("../../mol-geo/geometry/points/points-builder");
exports.VolumeDotParams = {
    isoValue: volume_1.Volume.IsoValueParam,
};
//
exports.VolumeSphereParams = {
    ...spheres_1.Spheres.Params,
    ...mesh_1.Mesh.Params,
    ...exports.VolumeDotParams,
    tryUseImpostor: param_definition_1.ParamDefinition.Boolean(true),
    detail: param_definition_1.ParamDefinition.Numeric(0, { min: 0, max: 3, step: 1 }, base_1.BaseGeometry.CustomQualityParamInfo),
};
function VolumeSphereVisual(materialId, volume, key, props, webgl) {
    return props.tryUseImpostor && webgl && webgl.extensions.fragDepth && webgl.extensions.textureFloat
        ? VolumeSphereImpostorVisual(materialId)
        : VolumeSphereMeshVisual(materialId);
}
function VolumeSphereImpostorVisual(materialId) {
    return (0, representation_1.VolumeVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.VolumeSphereParams),
        createGeometry: createVolumeSphereImpostor,
        createLocationIterator: util_1.createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!volume_1.Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats));
        },
        geometryUtils: spheres_1.Spheres.Utils,
        mustRecreate: (volumekey, props, webgl) => {
            return !props.tryUseImpostor || !webgl;
        }
    }, materialId);
}
function VolumeSphereMeshVisual(materialId) {
    return (0, representation_1.VolumeVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.VolumeSphereParams),
        createGeometry: createVolumeSphereMesh,
        createLocationIterator: util_1.createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!volume_1.Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats) ||
                newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail);
        },
        geometryUtils: mesh_1.Mesh.Utils,
        mustRecreate: (volumekey, props, webgl) => {
            return props.tryUseImpostor && !!webgl;
        }
    }, materialId);
}
function createVolumeSphereImpostor(ctx, volume, key, theme, props, spheres) {
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = volume_1.Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = volume_1.Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = (0, vec3_1.Vec3)();
    const [xn, yn, zn] = space.dimensions;
    const count = Math.ceil((xn * yn * zn) / 10);
    const builder = spheres_builder_1.SpheresBuilder.create(count, Math.ceil(count / 2), spheres);
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                vec3_1.Vec3.set(p, x, y, z);
                vec3_1.Vec3.transformMat4(p, p, gridToCartn);
                builder.add(p[0], p[1], p[2], space.dataOffset(x, y, z));
            }
        }
    }
    const s = builder.getSpheres();
    s.setBoundingSphere(volume_1.Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return s;
}
function createVolumeSphereMesh(ctx, volume, key, theme, props, mesh) {
    const { detail, sizeFactor } = props;
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = volume_1.Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = volume_1.Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = (0, vec3_1.Vec3)();
    const [xn, yn, zn] = space.dimensions;
    const count = (xn * yn * zn) / 10;
    const vertexCount = count * (0, sphere_2.sphereVertexCount)(detail);
    const builderState = mesh_builder_1.MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const l = volume_1.Volume.Cell.Location(volume);
    const themeSize = theme.size.size;
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                vec3_1.Vec3.set(p, x, y, z);
                vec3_1.Vec3.transformMat4(p, p, gridToCartn);
                builderState.currentGroup = space.dataOffset(x, y, z);
                l.cell = builderState.currentGroup;
                const size = themeSize(l);
                (0, sphere_1.addSphere)(builderState, p, size * sizeFactor, detail);
            }
        }
    }
    const m = mesh_builder_1.MeshBuilder.getMesh(builderState);
    m.setBoundingSphere(volume_1.Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return m;
}
//
exports.VolumePointParams = {
    ...points_1.Points.Params,
    ...exports.VolumeDotParams,
};
function VolumePointVisual(materialId) {
    return (0, representation_1.VolumeVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.VolumePointParams),
        createGeometry: createVolumePoint,
        createLocationIterator: util_1.createVolumeCellLocationIterator,
        getLoci: getDotLoci,
        eachLocation: eachDot,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = (!volume_1.Volume.IsoValue.areSame(newProps.isoValue, currentProps.isoValue, volume.grid.stats));
        },
        geometryUtils: points_1.Points.Utils,
    }, materialId);
}
function createVolumePoint(ctx, volume, key, theme, props, points) {
    const { cells: { space, data }, stats } = volume.grid;
    const gridToCartn = volume_1.Grid.getGridToCartesianTransform(volume.grid);
    const isoVal = volume_1.Volume.IsoValue.toAbsolute(props.isoValue, stats).absoluteValue;
    const p = (0, vec3_1.Vec3)();
    const [xn, yn, zn] = space.dimensions;
    const count = Math.ceil((xn * yn * zn) / 10);
    const builder = points_builder_1.PointsBuilder.create(count, Math.ceil(count / 2), points);
    for (let z = 0; z < zn; ++z) {
        for (let y = 0; y < yn; ++y) {
            for (let x = 0; x < xn; ++x) {
                if (space.get(data, x, y, z) < isoVal)
                    continue;
                vec3_1.Vec3.set(p, x, y, z);
                vec3_1.Vec3.transformMat4(p, p, gridToCartn);
                builder.add(p[0], p[1], p[2], space.dataOffset(x, y, z));
            }
        }
    }
    const pt = builder.getPoints();
    pt.setBoundingSphere(volume_1.Volume.Isosurface.getBoundingSphere(volume, props.isoValue));
    return pt;
}
//
function getLoci(volume, props) {
    return volume_1.Volume.Isosurface.Loci(volume, props.isoValue);
}
function getDotLoci(pickingId, volume, key, props, id) {
    const { objectId, groupId } = pickingId;
    if (id === objectId) {
        const granularity = volume_1.Volume.PickingGranularity.get(volume);
        if (granularity === 'volume') {
            return volume_1.Volume.Loci(volume);
        }
        else if (granularity === 'object') {
            return volume_1.Volume.Isosurface.Loci(volume, props.isoValue);
        }
        else {
            return volume_1.Volume.Cell.Loci(volume, int_1.Interval.ofSingleton(groupId));
        }
    }
    return loci_1.EmptyLoci;
}
function eachDot(loci, volume, key, props, apply) {
    return (0, util_1.eachVolumeLoci)(loci, volume, { isoValue: props.isoValue }, apply);
}
//
const DotVisuals = {
    'sphere': (ctx, getParams) => (0, representation_1.VolumeRepresentation)('Dot sphere', ctx, getParams, VolumeSphereVisual, getLoci),
    'point': (ctx, getParams) => (0, representation_1.VolumeRepresentation)('Dot point', ctx, getParams, VolumePointVisual, getLoci),
};
exports.DotParams = {
    ...exports.VolumeSphereParams,
    ...exports.VolumePointParams,
    visuals: param_definition_1.ParamDefinition.MultiSelect(['sphere'], param_definition_1.ParamDefinition.objectToOptions(DotVisuals)),
    bumpFrequency: param_definition_1.ParamDefinition.Numeric(1, { min: 0, max: 10, step: 0.1 }, base_1.BaseGeometry.ShadingCategory),
};
function getDotParams(ctx, volume) {
    const p = param_definition_1.ParamDefinition.clone(exports.DotParams);
    p.isoValue = volume_1.Volume.createIsoValueParam(volume_1.Volume.IsoValue.relative(2), volume.grid.stats);
    return p;
}
function DotRepresentation(ctx, getParams) {
    return representation_2.Representation.createMulti('Dot', ctx, getParams, representation_2.Representation.StateBuilder, DotVisuals);
}
exports.DotRepresentationProvider = (0, representation_1.VolumeRepresentationProvider)({
    name: 'dot',
    label: 'Dot',
    description: 'Displays dots of volumetric data.',
    factory: DotRepresentation,
    getParams: getDotParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.DotParams),
    defaultColorTheme: { name: 'uniform' },
    defaultSizeTheme: { name: 'uniform' },
    isApplicable: (volume) => !volume_1.Volume.isEmpty(volume) && !volume_1.Volume.Segmentation.get(volume)
});
