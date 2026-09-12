/**
 * Copyright (c) 2020 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Scene } from '../../mol-gl/scene';
import { WebGLContext } from '../../mol-gl/webgl/context';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { BoundingSphereHelper } from './bounding-sphere-helper';
import { CameraHelper } from './camera-helper';
import { HandleHelper } from './handle-helper';
export declare const HelperParams: {
    debug: PD.Group<PD.Normalize<{
        sceneBoundingSpheres: boolean;
        visibleSceneBoundingSpheres: boolean;
        objectBoundingSpheres: boolean;
        instanceBoundingSpheres: boolean;
    }>>;
    camera: PD.Group<PD.Normalize<{
        helper: PD.Normalize<{
            axes: /*elided*/ any;
        }>;
    }>>;
    handle: PD.Group<PD.Normalize<{
        handle: PD.NamedParams<PD.Normalize<unknown>, "off"> | PD.NamedParams<PD.Normalize<{
            alpha: /*elided*/ any;
            ignoreLight: /*elided*/ any;
            colorX: /*elided*/ any;
            colorY: /*elided*/ any;
            colorZ: /*elided*/ any;
            scale: /*elided*/ any;
            doubleSided: /*elided*/ any;
            flipSided: /*elided*/ any;
            flatShaded: /*elided*/ any;
            celShaded: /*elided*/ any;
            xrayShaded: /*elided*/ any;
            transparentBackfaces: /*elided*/ any;
            bumpFrequency: /*elided*/ any;
            bumpAmplitude: /*elided*/ any;
            quality: /*elided*/ any;
            material: /*elided*/ any;
            clip: /*elided*/ any;
            emissive: /*elided*/ any;
            density: /*elided*/ any;
            instanceGranularity: /*elided*/ any;
            lod: /*elided*/ any;
            cellSize: /*elided*/ any;
            batchSize: /*elided*/ any;
        }>, "on">;
    }>>;
};
export declare const DefaultHelperProps: PD.Values<{
    debug: PD.Group<PD.Normalize<{
        sceneBoundingSpheres: boolean;
        visibleSceneBoundingSpheres: boolean;
        objectBoundingSpheres: boolean;
        instanceBoundingSpheres: boolean;
    }>>;
    camera: PD.Group<PD.Normalize<{
        helper: PD.Normalize<{
            axes: /*elided*/ any;
        }>;
    }>>;
    handle: PD.Group<PD.Normalize<{
        handle: PD.NamedParams<PD.Normalize<unknown>, "off"> | PD.NamedParams<PD.Normalize<{
            alpha: /*elided*/ any;
            ignoreLight: /*elided*/ any;
            colorX: /*elided*/ any;
            colorY: /*elided*/ any;
            colorZ: /*elided*/ any;
            scale: /*elided*/ any;
            doubleSided: /*elided*/ any;
            flipSided: /*elided*/ any;
            flatShaded: /*elided*/ any;
            celShaded: /*elided*/ any;
            xrayShaded: /*elided*/ any;
            transparentBackfaces: /*elided*/ any;
            bumpFrequency: /*elided*/ any;
            bumpAmplitude: /*elided*/ any;
            quality: /*elided*/ any;
            material: /*elided*/ any;
            clip: /*elided*/ any;
            emissive: /*elided*/ any;
            density: /*elided*/ any;
            instanceGranularity: /*elided*/ any;
            lod: /*elided*/ any;
            cellSize: /*elided*/ any;
            batchSize: /*elided*/ any;
        }>, "on">;
    }>>;
}>;
export type HelperProps = PD.Values<typeof HelperParams>;
export declare class Helper {
    readonly debug: BoundingSphereHelper;
    readonly camera: CameraHelper;
    readonly handle: HandleHelper;
    constructor(webgl: WebGLContext, scene: Scene, props?: Partial<HelperProps>);
}
