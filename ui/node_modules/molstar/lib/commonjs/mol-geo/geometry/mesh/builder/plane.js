"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.addPlane = addPlane;
const linear_algebra_1 = require("../../../../mol-math/linear-algebra");
const plane_1 = require("../../../primitive/plane");
const mesh_builder_1 = require("../mesh-builder");
const tmpPlaneMat = linear_algebra_1.Mat4.identity();
const tmpVec = (0, linear_algebra_1.Vec3)();
function setPlaneMat(m, center, dirMajor, dirMinor, scale) {
    linear_algebra_1.Vec3.add(tmpVec, center, dirMajor);
    linear_algebra_1.Mat4.targetTo(m, center, tmpVec, dirMinor);
    linear_algebra_1.Mat4.setTranslation(m, center);
    linear_algebra_1.Mat4.mul(m, m, linear_algebra_1.Mat4.rotY90);
    return linear_algebra_1.Mat4.scale(m, m, scale);
}
function addPlane(state, center, dirMajor, dirMinor, scale, widthSegments, heightSegments) {
    const plane = (0, plane_1.SegmentedPlane)(widthSegments, heightSegments);
    mesh_builder_1.MeshBuilder.addPrimitive(state, setPlaneMat(tmpPlaneMat, center, dirMajor, dirMinor, scale), plane);
}
