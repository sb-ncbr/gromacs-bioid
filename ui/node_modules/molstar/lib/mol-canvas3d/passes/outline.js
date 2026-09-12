/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Áron Samuel Kovács <aron.kovacs@mail.muni.cz>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 * @author Gianluca Tomasello <giagitom@gmail.com>
 */
import { QuadSchema, QuadValues } from '../../mol-gl/compute/util';
import { TextureSpec, UniformSpec, DefineSpec } from '../../mol-gl/renderable/schema';
import { ShaderCode } from '../../mol-gl/shader-code';
import { ValueCell } from '../../mol-util';
import { createComputeRenderItem } from '../../mol-gl/webgl/render-item';
import { createComputeRenderable } from '../../mol-gl/renderable';
import { Mat4, Vec2 } from '../../mol-math/linear-algebra';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { quad_vert } from '../../mol-gl/shader/quad.vert';
import { outlines_frag } from '../../mol-gl/shader/outlines.frag';
import { isTimingMode } from '../../mol-util/debug';
import { Color } from '../../mol-util/color';
export const OutlineParams = {
    scale: PD.Numeric(1, { min: 1, max: 5, step: 1 }),
    threshold: PD.Numeric(0.33, { min: 0.01, max: 1, step: 0.01 }),
    color: PD.Color(Color(0x000000)),
    includeTransparent: PD.Boolean(true, { description: 'Whether to show outline for transparent objects' }),
};
export class OutlinePass {
    static isEnabled(props) {
        return props.outline.name !== 'off';
    }
    constructor(webgl, width, height, depthTextureTransparent, depthTextureOpaque) {
        this.webgl = webgl;
        this.target = webgl.createRenderTarget(width, height, false);
        this.renderable = getOutlinesRenderable(webgl, depthTextureOpaque, depthTextureTransparent, true);
    }
    setSize(width, height) {
        const [w, h] = this.renderable.values.uTexSize.ref.value;
        if (width !== w || height !== h) {
            this.target.setSize(width, height);
            ValueCell.update(this.renderable.values.uTexSize, Vec2.set(this.renderable.values.uTexSize.ref.value, width, height));
        }
    }
    update(camera, props, depthTextureTransparent, depthTextureOpaque) {
        var _a;
        let needsUpdate = false;
        const orthographic = camera.state.mode === 'orthographic' ? 1 : 0;
        const invProjection = this.renderable.values.uInvProjection.ref.value;
        Mat4.invert(invProjection, camera.projection);
        const transparentOutline = (_a = props.includeTransparent) !== null && _a !== void 0 ? _a : true;
        const outlineScale = Math.max(1, Math.round(props.scale * this.webgl.pixelRatio)) - 1;
        const outlineThreshold = 50 * props.threshold * this.webgl.pixelRatio;
        ValueCell.updateIfChanged(this.renderable.values.uNear, camera.near);
        ValueCell.updateIfChanged(this.renderable.values.uFar, camera.far);
        ValueCell.update(this.renderable.values.uInvProjection, invProjection);
        if (this.renderable.values.dTransparentOutline.ref.value !== transparentOutline) {
            needsUpdate = true;
            ValueCell.update(this.renderable.values.dTransparentOutline, transparentOutline);
        }
        if (this.renderable.values.dOrthographic.ref.value !== orthographic) {
            needsUpdate = true;
            ValueCell.update(this.renderable.values.dOrthographic, orthographic);
        }
        ValueCell.updateIfChanged(this.renderable.values.uOutlineThreshold, outlineThreshold);
        if (this.renderable.values.tDepthTransparent.ref.value !== depthTextureTransparent) {
            needsUpdate = true;
            ValueCell.update(this.renderable.values.tDepthTransparent, depthTextureTransparent);
        }
        if (this.renderable.values.tDepthOpaque.ref.value !== depthTextureOpaque) {
            needsUpdate = true;
            ValueCell.update(this.renderable.values.tDepthOpaque, depthTextureOpaque);
        }
        if (needsUpdate) {
            this.renderable.update();
        }
        return { transparentOutline, outlineScale };
    }
    render() {
        if (isTimingMode)
            this.webgl.timer.mark('OutlinePass.render');
        this.target.bind();
        this.renderable.render();
        if (isTimingMode)
            this.webgl.timer.markEnd('OutlinePass.render');
    }
}
export const OutlinesSchema = {
    ...QuadSchema,
    tDepthOpaque: TextureSpec('texture', 'rgba', 'ubyte', 'nearest'),
    tDepthTransparent: TextureSpec('texture', 'rgba', 'ubyte', 'nearest'),
    uTexSize: UniformSpec('v2'),
    dOrthographic: DefineSpec('number'),
    uNear: UniformSpec('f'),
    uFar: UniformSpec('f'),
    uInvProjection: UniformSpec('m4'),
    uOutlineThreshold: UniformSpec('f'),
    dTransparentOutline: DefineSpec('boolean'),
};
export function getOutlinesRenderable(ctx, depthTextureOpaque, depthTextureTransparent, transparentOutline) {
    const width = depthTextureOpaque.getWidth();
    const height = depthTextureOpaque.getHeight();
    const values = {
        ...QuadValues,
        tDepthOpaque: ValueCell.create(depthTextureOpaque),
        tDepthTransparent: ValueCell.create(depthTextureTransparent),
        uTexSize: ValueCell.create(Vec2.create(width, height)),
        dOrthographic: ValueCell.create(0),
        uNear: ValueCell.create(1),
        uFar: ValueCell.create(10000),
        uInvProjection: ValueCell.create(Mat4.identity()),
        uOutlineThreshold: ValueCell.create(0.33),
        dTransparentOutline: ValueCell.create(transparentOutline),
    };
    const schema = { ...OutlinesSchema };
    const shaderCode = ShaderCode('outlines', quad_vert, outlines_frag);
    const renderItem = createComputeRenderItem(ctx, 'triangles', shaderCode, schema, values);
    return createComputeRenderable(renderItem, values);
}
