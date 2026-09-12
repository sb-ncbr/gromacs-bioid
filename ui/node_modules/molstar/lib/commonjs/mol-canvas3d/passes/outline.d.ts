/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Áron Samuel Kovács <aron.kovacs@mail.muni.cz>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 * @author Gianluca Tomasello <giagitom@gmail.com>
 */
import { TextureSpec, Values, UniformSpec, DefineSpec } from '../../mol-gl/renderable/schema';
import { WebGLContext } from '../../mol-gl/webgl/context';
import { Texture } from '../../mol-gl/webgl/texture';
import { ComputeRenderable } from '../../mol-gl/renderable';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { RenderTarget } from '../../mol-gl/webgl/render-target';
import { ICamera } from '../../mol-canvas3d/camera';
import { PostprocessingProps } from './postprocessing';
export declare const OutlineParams: {
    scale: PD.Numeric;
    threshold: PD.Numeric;
    color: PD.Color;
    includeTransparent: PD.BooleanParam;
};
export type OutlineProps = PD.Values<typeof OutlineParams>;
export declare class OutlinePass {
    private readonly webgl;
    static isEnabled(props: PostprocessingProps): boolean;
    readonly target: RenderTarget;
    private readonly renderable;
    constructor(webgl: WebGLContext, width: number, height: number, depthTextureTransparent: Texture, depthTextureOpaque: Texture);
    setSize(width: number, height: number): void;
    update(camera: ICamera, props: OutlineProps, depthTextureTransparent: Texture, depthTextureOpaque: Texture): {
        transparentOutline: boolean;
        outlineScale: number;
    };
    render(): void;
}
export declare const OutlinesSchema: {
    tDepthOpaque: TextureSpec<"texture">;
    tDepthTransparent: TextureSpec<"texture">;
    uTexSize: UniformSpec<"v2">;
    dOrthographic: DefineSpec<"number">;
    uNear: UniformSpec<"f">;
    uFar: UniformSpec<"f">;
    uInvProjection: UniformSpec<"m4">;
    uOutlineThreshold: UniformSpec<"f">;
    dTransparentOutline: DefineSpec<"boolean">;
    drawCount: import("../../mol-gl/renderable/schema").ValueSpec<"number">;
    instanceCount: import("../../mol-gl/renderable/schema").ValueSpec<"number">;
    aPosition: import("../../mol-gl/renderable/schema").AttributeSpec<"float32">;
    uQuadScale: UniformSpec<"v2">;
};
export type OutlinesRenderable = ComputeRenderable<Values<typeof OutlinesSchema>>;
export declare function getOutlinesRenderable(ctx: WebGLContext, depthTextureOpaque: Texture, depthTextureTransparent: Texture, transparentOutline: boolean): OutlinesRenderable;
