"use strict";
/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Áron Samuel Kovács <aron.kovacs@mail.muni.cz>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 * @author Gianluca Tomasello <giagitom@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ShadowPass = exports.ShadowParams = void 0;
const util_1 = require("../../mol-gl/compute/util");
const schema_1 = require("../../mol-gl/renderable/schema");
const shader_code_1 = require("../../mol-gl/shader-code");
const mol_util_1 = require("../../mol-util");
const render_item_1 = require("../../mol-gl/webgl/render-item");
const renderable_1 = require("../../mol-gl/renderable");
const linear_algebra_1 = require("../../mol-math/linear-algebra");
const param_definition_1 = require("../../mol-util/param-definition");
const quad_vert_1 = require("../../mol-gl/shader/quad.vert");
const debug_1 = require("../../mol-util/debug");
const shadows_frag_1 = require("../../mol-gl/shader/shadows.frag");
exports.ShadowParams = {
    steps: param_definition_1.ParamDefinition.Numeric(1, { min: 1, max: 64, step: 1 }),
    maxDistance: param_definition_1.ParamDefinition.Numeric(3, { min: 0, max: 256, step: 1 }),
    tolerance: param_definition_1.ParamDefinition.Numeric(1.0, { min: 0.0, max: 10.0, step: 0.1 }),
};
class ShadowPass {
    static isEnabled(props) {
        return props.shadow.name !== 'off';
    }
    constructor(webgl, width, height, depthTextureOpaque) {
        this.webgl = webgl;
        this.target = webgl.createRenderTarget(width, height, false);
        this.renderable = getShadowsRenderable(webgl, depthTextureOpaque);
    }
    setSize(width, height) {
        const [w, h] = this.renderable.values.uTexSize.ref.value;
        if (width !== w || height !== h) {
            this.target.setSize(width, height);
            mol_util_1.ValueCell.update(this.renderable.values.uTexSize, linear_algebra_1.Vec2.set(this.renderable.values.uTexSize.ref.value, width, height));
        }
    }
    update(camera, light, ambientColor, props) {
        let needsUpdateShadows = false;
        const orthographic = camera.state.mode === 'orthographic' ? 1 : 0;
        const invProjection = linear_algebra_1.Mat4.identity();
        linear_algebra_1.Mat4.invert(invProjection, camera.projection);
        const [w, h] = this.renderable.values.uTexSize.ref.value;
        const v = camera.viewport;
        mol_util_1.ValueCell.update(this.renderable.values.uProjection, camera.projection);
        mol_util_1.ValueCell.update(this.renderable.values.uInvProjection, invProjection);
        linear_algebra_1.Vec4.set(this.renderable.values.uBounds.ref.value, v.x / w, v.y / h, (v.x + v.width) / w, (v.y + v.height) / h);
        mol_util_1.ValueCell.update(this.renderable.values.uBounds, this.renderable.values.uBounds.ref.value);
        mol_util_1.ValueCell.updateIfChanged(this.renderable.values.uNear, camera.near);
        mol_util_1.ValueCell.updateIfChanged(this.renderable.values.uFar, camera.far);
        if (this.renderable.values.dOrthographic.ref.value !== orthographic) {
            mol_util_1.ValueCell.update(this.renderable.values.dOrthographic, orthographic);
            needsUpdateShadows = true;
        }
        mol_util_1.ValueCell.updateIfChanged(this.renderable.values.uMaxDistance, props.maxDistance);
        mol_util_1.ValueCell.updateIfChanged(this.renderable.values.uTolerance, props.tolerance);
        if (this.renderable.values.dSteps.ref.value !== props.steps) {
            mol_util_1.ValueCell.update(this.renderable.values.dSteps, props.steps);
            needsUpdateShadows = true;
        }
        mol_util_1.ValueCell.update(this.renderable.values.uLightDirection, light.direction);
        mol_util_1.ValueCell.update(this.renderable.values.uLightColor, light.color);
        if (this.renderable.values.dLightCount.ref.value !== light.count) {
            mol_util_1.ValueCell.update(this.renderable.values.dLightCount, light.count);
            needsUpdateShadows = true;
        }
        mol_util_1.ValueCell.update(this.renderable.values.uAmbientColor, ambientColor);
        if (needsUpdateShadows) {
            this.renderable.update();
        }
    }
    render() {
        if (debug_1.isTimingMode)
            this.webgl.timer.mark('ShadowPass.render');
        this.target.bind();
        this.renderable.render();
        if (debug_1.isTimingMode)
            this.webgl.timer.markEnd('ShadowPass.render');
    }
}
exports.ShadowPass = ShadowPass;
const ShadowsSchema = {
    ...util_1.QuadSchema,
    tDepth: (0, schema_1.TextureSpec)('texture', 'rgba', 'ubyte', 'nearest'),
    uTexSize: (0, schema_1.UniformSpec)('v2'),
    uProjection: (0, schema_1.UniformSpec)('m4'),
    uInvProjection: (0, schema_1.UniformSpec)('m4'),
    uBounds: (0, schema_1.UniformSpec)('v4'),
    dOrthographic: (0, schema_1.DefineSpec)('number'),
    uNear: (0, schema_1.UniformSpec)('f'),
    uFar: (0, schema_1.UniformSpec)('f'),
    dSteps: (0, schema_1.DefineSpec)('number'),
    uMaxDistance: (0, schema_1.UniformSpec)('f'),
    uTolerance: (0, schema_1.UniformSpec)('f'),
    uLightDirection: (0, schema_1.UniformSpec)('v3[]'),
    uLightColor: (0, schema_1.UniformSpec)('v3[]'),
    dLightCount: (0, schema_1.DefineSpec)('number'),
    uAmbientColor: (0, schema_1.UniformSpec)('v3'),
};
function getShadowsRenderable(ctx, depthTexture) {
    const width = depthTexture.getWidth();
    const height = depthTexture.getHeight();
    const values = {
        ...util_1.QuadValues,
        tDepth: mol_util_1.ValueCell.create(depthTexture),
        uTexSize: mol_util_1.ValueCell.create(linear_algebra_1.Vec2.create(width, height)),
        uProjection: mol_util_1.ValueCell.create(linear_algebra_1.Mat4.identity()),
        uInvProjection: mol_util_1.ValueCell.create(linear_algebra_1.Mat4.identity()),
        uBounds: mol_util_1.ValueCell.create((0, linear_algebra_1.Vec4)()),
        dOrthographic: mol_util_1.ValueCell.create(0),
        uNear: mol_util_1.ValueCell.create(1),
        uFar: mol_util_1.ValueCell.create(10000),
        dSteps: mol_util_1.ValueCell.create(1),
        uMaxDistance: mol_util_1.ValueCell.create(3.0),
        uTolerance: mol_util_1.ValueCell.create(1.0),
        uLightDirection: mol_util_1.ValueCell.create([]),
        uLightColor: mol_util_1.ValueCell.create([]),
        dLightCount: mol_util_1.ValueCell.create(0),
        uAmbientColor: mol_util_1.ValueCell.create((0, linear_algebra_1.Vec3)()),
    };
    const schema = { ...ShadowsSchema };
    const shaderCode = (0, shader_code_1.ShaderCode)('shadows', quad_vert_1.quad_vert, shadows_frag_1.shadows_frag);
    const renderItem = (0, render_item_1.createComputeRenderItem)(ctx, 'triangles', shaderCode, schema, values);
    return (0, renderable_1.createComputeRenderable)(renderItem, values);
}
