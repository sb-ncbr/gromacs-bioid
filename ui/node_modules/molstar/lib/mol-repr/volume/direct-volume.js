/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { Vec3, Mat4 } from '../../mol-math/linear-algebra';
import { Box3D } from '../../mol-math/geometry';
import { Grid, Volume } from '../../mol-model/volume';
import { DirectVolume } from '../../mol-geo/geometry/direct-volume/direct-volume';
import { VolumeVisual, VolumeRepresentation, VolumeRepresentationProvider } from './representation';
import { LocationIterator } from '../../mol-geo/util/location-iterator';
import { NullLocation } from '../../mol-model/location';
import { Interval } from '../../mol-data/int';
import { EmptyLoci } from '../../mol-model/loci';
import { createVolumeTexture2d, createVolumeTexture3d, eachVolumeLoci, getVolumeTexture2dLayout } from './util';
function getBoundingBox(gridDimension, transform) {
    const bbox = Box3D();
    Box3D.add(bbox, gridDimension);
    Box3D.transform(bbox, bbox, transform);
    return bbox;
}
// 2d volume texture
export function createDirectVolume2d(ctx, webgl, volume, props, directVolume) {
    const gridDimension = volume.grid.cells.space.dimensions;
    const { width, height } = getVolumeTexture2dLayout(gridDimension);
    if (Math.max(width, height) > webgl.maxTextureSize / 2) {
        throw new Error('volume too large for direct-volume rendering');
    }
    const dataType = props.dataType === 'halfFloat' && !webgl.extensions.textureHalfFloat ? 'float' : props.dataType;
    const textureImage = createVolumeTexture2d(volume, 'normals', 0, dataType);
    // debugTexture(createImageData(textureImage.array, textureImage.width, textureImage.height), 1/3)
    const transform = Grid.getGridToCartesianTransform(volume.grid);
    const bbox = getBoundingBox(gridDimension, transform);
    let texture;
    if (directVolume && directVolume.dataType.ref.value === dataType) {
        texture = directVolume.gridTexture.ref.value;
    }
    else {
        texture = dataType === 'byte'
            ? webgl.resources.texture('image-uint8', 'rgba', 'ubyte', 'linear')
            : dataType === 'halfFloat'
                ? webgl.resources.texture('image-float16', 'rgba', 'fp16', 'linear')
                : webgl.resources.texture('image-float32', 'rgba', 'float', 'linear');
    }
    texture.load(textureImage);
    const { unitToCartn, cellDim } = getUnitToCartn(volume.grid);
    const axisOrder = volume.grid.cells.space.axisOrderSlowToFast;
    return DirectVolume.create(bbox, gridDimension, transform, unitToCartn, cellDim, texture, volume.grid.stats, false, axisOrder, dataType, directVolume);
}
// 3d volume texture
function getUnitToCartn(grid) {
    if (grid.transform.kind === 'matrix') {
        return {
            unitToCartn: Mat4.mul(Mat4(), grid.transform.matrix, Mat4.fromScaling(Mat4(), grid.cells.space.dimensions)),
            cellDim: Mat4.getScaling(Vec3(), grid.transform.matrix)
        };
    }
    const box = grid.transform.fractionalBox;
    const size = Box3D.size(Vec3(), box);
    return {
        unitToCartn: Mat4.mul3(Mat4(), grid.transform.cell.fromFractional, Mat4.fromTranslation(Mat4(), box.min), Mat4.fromScaling(Mat4(), size)),
        cellDim: Vec3.div(Vec3(), grid.transform.cell.size, grid.cells.space.dimensions)
    };
}
export function createDirectVolume3d(ctx, webgl, volume, props, directVolume) {
    const gridDimension = volume.grid.cells.space.dimensions;
    if (Math.max(...gridDimension) > webgl.max3dTextureSize / 2) {
        throw new Error('volume too large for direct-volume rendering');
    }
    const dataType = props.dataType === 'halfFloat' && !webgl.extensions.textureHalfFloat ? 'float' : props.dataType;
    const textureVolume = createVolumeTexture3d(volume, dataType);
    const transform = Grid.getGridToCartesianTransform(volume.grid);
    const bbox = getBoundingBox(gridDimension, transform);
    let texture;
    if (directVolume && directVolume.dataType.ref.value === dataType) {
        texture = directVolume.gridTexture.ref.value;
    }
    else {
        texture = dataType === 'byte'
            ? webgl.resources.texture('volume-uint8', 'rgba', 'ubyte', 'linear')
            : dataType === 'halfFloat'
                ? webgl.resources.texture('volume-float16', 'rgba', 'fp16', 'linear')
                : webgl.resources.texture('volume-float32', 'rgba', 'float', 'linear');
    }
    texture.load(textureVolume);
    const { unitToCartn, cellDim } = getUnitToCartn(volume.grid);
    const axisOrder = volume.grid.cells.space.axisOrderSlowToFast;
    return DirectVolume.create(bbox, gridDimension, transform, unitToCartn, cellDim, texture, volume.grid.stats, false, axisOrder, dataType, directVolume);
}
//
export async function createDirectVolume(ctx, volume, key, theme, props, directVolume) {
    const { runtime, webgl } = ctx;
    if (webgl === undefined)
        throw new Error('DirectVolumeVisual requires `webgl` in VisualContext');
    return webgl.isWebGL2 ?
        createDirectVolume3d(runtime, webgl, volume, props, directVolume) :
        createDirectVolume2d(runtime, webgl, volume, props, directVolume);
}
function getLoci(volume, props) {
    return Volume.Loci(volume);
}
export function getDirectVolumeLoci(pickingId, volume, key, props, id) {
    const { objectId, groupId } = pickingId;
    if (id === objectId) {
        return Volume.Cell.Loci(volume, Interval.ofSingleton(groupId));
    }
    return EmptyLoci;
}
export function eachDirectVolume(loci, volume, key, props, apply) {
    return eachVolumeLoci(loci, volume, undefined, apply);
}
//
export const DirectVolumeParams = {
    ...DirectVolume.Params,
    quality: { ...DirectVolume.Params.quality, isEssential: false },
    dataType: PD.Select('byte', PD.arrayToOptions(['byte', 'float', 'halfFloat'])),
};
export function getDirectVolumeParams(ctx, volume) {
    const params = PD.clone(DirectVolumeParams);
    params.controlPoints.getVolume = () => volume;
    return params;
}
export function DirectVolumeVisual(materialId) {
    return VolumeVisual({
        defaultProps: PD.getDefaultValues(DirectVolumeParams),
        createGeometry: createDirectVolume,
        createLocationIterator: (volume) => LocationIterator(volume.grid.cells.data.length, 1, 1, () => NullLocation),
        getLoci: getDirectVolumeLoci,
        eachLocation: eachDirectVolume,
        setUpdateState: (state, volume, newProps, currentProps) => {
            state.createGeometry = newProps.dataType !== currentProps.dataType;
        },
        geometryUtils: DirectVolume.Utils,
        dispose: (geometry) => {
            geometry.gridTexture.ref.value.destroy();
        },
    }, materialId);
}
export function DirectVolumeRepresentation(ctx, getParams) {
    return VolumeRepresentation('Direct Volume', ctx, getParams, DirectVolumeVisual, getLoci);
}
export const DirectVolumeRepresentationProvider = VolumeRepresentationProvider({
    name: 'direct-volume',
    label: 'Direct Volume',
    description: 'Direct rendering of volumetric data.',
    factory: DirectVolumeRepresentation,
    getParams: getDirectVolumeParams,
    defaultValues: PD.getDefaultValues(DirectVolumeParams),
    defaultColorTheme: { name: 'volume-value' },
    defaultSizeTheme: { name: 'uniform' },
    locationKinds: ['position-location', 'direct-location'],
    isApplicable: (volume) => !Volume.isEmpty(volume) && !Volume.Segmentation.get(volume)
});
