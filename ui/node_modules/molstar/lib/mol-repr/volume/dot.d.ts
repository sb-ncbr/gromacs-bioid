/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { Volume } from '../../mol-model/volume';
import { VisualContext } from '../visual';
import { Theme, ThemeRegistryContext } from '../../mol-theme/theme';
import { Mesh } from '../../mol-geo/geometry/mesh/mesh';
import { VolumeVisual, VolumeRepresentation, VolumeRepresentationProvider } from './representation';
import { RepresentationContext, RepresentationParamsGetter } from '../representation';
import { WebGLContext } from '../../mol-gl/webgl/context';
import { Spheres } from '../../mol-geo/geometry/spheres/spheres';
import { Points } from '../../mol-geo/geometry/points/points';
export declare const VolumeDotParams: {
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
};
export type VolumeDotParams = typeof VolumeDotParams;
export type VolumeDotProps = PD.Values<VolumeDotParams>;
export declare const VolumeSphereParams: {
    tryUseImpostor: PD.BooleanParam;
    detail: PD.Numeric;
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    doubleSided: PD.BooleanParam;
    flipSided: PD.BooleanParam;
    flatShaded: PD.BooleanParam;
    ignoreLight: PD.BooleanParam;
    celShaded: PD.BooleanParam;
    xrayShaded: PD.Select<boolean | "inverted">;
    transparentBackfaces: PD.Select<"off" | "on" | "opaque">;
    bumpFrequency: PD.Numeric;
    bumpAmplitude: PD.Numeric;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
    sizeFactor: PD.Numeric;
    solidInterior: PD.BooleanParam;
    clipPrimitive: PD.BooleanParam;
    approximate: PD.BooleanParam;
    alphaThickness: PD.Numeric;
    lodLevels: PD.ObjectList<PD.Normalize<{
        minDistance: number;
        maxDistance: number;
        overlap: number;
        stride: number;
        scaleBias: number;
    }>>;
};
export type VolumeSphereParams = typeof VolumeSphereParams;
export type VolumeSphereProps = PD.Values<VolumeSphereParams>;
export declare function VolumeSphereVisual(materialId: number, volume: Volume, key: number, props: PD.Values<VolumeSphereParams>, webgl?: WebGLContext): VolumeVisual<{
    tryUseImpostor: PD.BooleanParam;
    detail: PD.Numeric;
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    doubleSided: PD.BooleanParam;
    flipSided: PD.BooleanParam;
    flatShaded: PD.BooleanParam;
    ignoreLight: PD.BooleanParam;
    celShaded: PD.BooleanParam;
    xrayShaded: PD.Select<boolean | "inverted">;
    transparentBackfaces: PD.Select<"off" | "on" | "opaque">;
    bumpFrequency: PD.Numeric;
    bumpAmplitude: PD.Numeric;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
    sizeFactor: PD.Numeric;
    solidInterior: PD.BooleanParam;
    clipPrimitive: PD.BooleanParam;
    approximate: PD.BooleanParam;
    alphaThickness: PD.Numeric;
    lodLevels: PD.ObjectList<PD.Normalize<{
        minDistance: number;
        maxDistance: number;
        overlap: number;
        stride: number;
        scaleBias: number;
    }>>;
}>;
export declare function VolumeSphereImpostorVisual(materialId: number): VolumeVisual<VolumeSphereParams>;
export declare function VolumeSphereMeshVisual(materialId: number): VolumeVisual<VolumeSphereParams>;
export declare function createVolumeSphereImpostor(ctx: VisualContext, volume: Volume, key: number, theme: Theme, props: VolumeSphereProps, spheres?: Spheres): Spheres;
export declare function createVolumeSphereMesh(ctx: VisualContext, volume: Volume, key: number, theme: Theme, props: VolumeSphereProps, mesh?: Mesh): Mesh;
export declare const VolumePointParams: {
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    sizeFactor: PD.Numeric;
    pointSizeAttenuation: PD.BooleanParam;
    pointStyle: PD.Select<"circle" | "square" | "fuzzy">;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
};
export type VolumePointParams = typeof VolumePointParams;
export type VolumePointProps = PD.Values<VolumePointParams>;
export declare function VolumePointVisual(materialId: number): VolumeVisual<VolumePointParams>;
export declare function createVolumePoint(ctx: VisualContext, volume: Volume, key: number, theme: Theme, props: VolumePointProps, points?: Points): Points;
export declare const DotParams: {
    visuals: PD.MultiSelect<"sphere" | "point">;
    bumpFrequency: PD.Numeric;
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    sizeFactor: PD.Numeric;
    pointSizeAttenuation: PD.BooleanParam;
    pointStyle: PD.Select<"circle" | "square" | "fuzzy">;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
    tryUseImpostor: PD.BooleanParam;
    detail: PD.Numeric;
    doubleSided: PD.BooleanParam;
    flipSided: PD.BooleanParam;
    flatShaded: PD.BooleanParam;
    ignoreLight: PD.BooleanParam;
    celShaded: PD.BooleanParam;
    xrayShaded: PD.Select<boolean | "inverted">;
    transparentBackfaces: PD.Select<"off" | "on" | "opaque">;
    bumpAmplitude: PD.Numeric;
    solidInterior: PD.BooleanParam;
    clipPrimitive: PD.BooleanParam;
    approximate: PD.BooleanParam;
    alphaThickness: PD.Numeric;
    lodLevels: PD.ObjectList<PD.Normalize<{
        minDistance: number;
        maxDistance: number;
        overlap: number;
        stride: number;
        scaleBias: number;
    }>>;
};
export type DotParams = typeof DotParams;
export declare function getDotParams(ctx: ThemeRegistryContext, volume: Volume): {
    visuals: PD.MultiSelect<"sphere" | "point">;
    bumpFrequency: PD.Numeric;
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    sizeFactor: PD.Numeric;
    pointSizeAttenuation: PD.BooleanParam;
    pointStyle: PD.Select<"circle" | "square" | "fuzzy">;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
    tryUseImpostor: PD.BooleanParam;
    detail: PD.Numeric;
    doubleSided: PD.BooleanParam;
    flipSided: PD.BooleanParam;
    flatShaded: PD.BooleanParam;
    ignoreLight: PD.BooleanParam;
    celShaded: PD.BooleanParam;
    xrayShaded: PD.Select<boolean | "inverted">;
    transparentBackfaces: PD.Select<"off" | "on" | "opaque">;
    bumpAmplitude: PD.Numeric;
    solidInterior: PD.BooleanParam;
    clipPrimitive: PD.BooleanParam;
    approximate: PD.BooleanParam;
    alphaThickness: PD.Numeric;
    lodLevels: PD.ObjectList<PD.Normalize<{
        minDistance: number;
        maxDistance: number;
        overlap: number;
        stride: number;
        scaleBias: number;
    }>>;
};
export type DotRepresentation = VolumeRepresentation<DotParams>;
export declare function DotRepresentation(ctx: RepresentationContext, getParams: RepresentationParamsGetter<Volume, DotParams>): DotRepresentation;
export declare const DotRepresentationProvider: VolumeRepresentationProvider<{
    visuals: PD.MultiSelect<"sphere" | "point">;
    bumpFrequency: PD.Numeric;
    isoValue: PD.Conditioned<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>, PD.Base<Readonly<{
        kind: "absolute";
        absoluteValue: number;
    }> | Readonly<{
        kind: "relative";
        relativeValue: number;
    }>>, {
        absolute: PD.Converted<Readonly<{
            kind: "absolute";
            absoluteValue: number;
        }>, number>;
        relative: PD.Converted<Readonly<{
            kind: "relative";
            relativeValue: number;
        }>, number>;
    }>;
    sizeFactor: PD.Numeric;
    pointSizeAttenuation: PD.BooleanParam;
    pointStyle: PD.Select<"circle" | "square" | "fuzzy">;
    alpha: PD.Numeric;
    quality: PD.Select<"auto" | "medium" | "high" | "low" | "custom" | "highest" | "higher" | "lower" | "lowest">;
    material: PD.Group<PD.Normalize<{
        metalness: number;
        roughness: number;
        bumpiness: number;
    }>>;
    clip: PD.Group<PD.Normalize<{
        variant: import("../../mol-util/clip").Clip.Variant;
        objects: PD.Normalize<{
            type: /*elided*/ any;
            invert: /*elided*/ any;
            position: /*elided*/ any;
            rotation: /*elided*/ any;
            scale: /*elided*/ any;
            transform: /*elided*/ any;
        }>[];
    }>>;
    emissive: PD.Numeric;
    density: PD.Numeric;
    instanceGranularity: PD.BooleanParam;
    lod: PD.Vec3;
    cellSize: PD.Numeric;
    batchSize: PD.Numeric;
    tryUseImpostor: PD.BooleanParam;
    detail: PD.Numeric;
    doubleSided: PD.BooleanParam;
    flipSided: PD.BooleanParam;
    flatShaded: PD.BooleanParam;
    ignoreLight: PD.BooleanParam;
    celShaded: PD.BooleanParam;
    xrayShaded: PD.Select<boolean | "inverted">;
    transparentBackfaces: PD.Select<"off" | "on" | "opaque">;
    bumpAmplitude: PD.Numeric;
    solidInterior: PD.BooleanParam;
    clipPrimitive: PD.BooleanParam;
    approximate: PD.BooleanParam;
    alphaThickness: PD.Numeric;
    lodLevels: PD.ObjectList<PD.Normalize<{
        minDistance: number;
        maxDistance: number;
        overlap: number;
        stride: number;
        scaleBias: number;
    }>>;
}, "dot">;
