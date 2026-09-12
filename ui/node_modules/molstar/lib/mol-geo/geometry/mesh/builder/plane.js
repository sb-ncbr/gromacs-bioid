/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Vec3, Mat4 } from '../../../../mol-math/linear-algebra';
import { SegmentedPlane } from '../../../primitive/plane';
import { MeshBuilder } from '../mesh-builder';
const tmpPlaneMat = Mat4.identity();
const tmpVec = Vec3();
function setPlaneMat(m, center, dirMajor, dirMinor, scale) {
    Vec3.add(tmpVec, center, dirMajor);
    Mat4.targetTo(m, center, tmpVec, dirMinor);
    Mat4.setTranslation(m, center);
    Mat4.mul(m, m, Mat4.rotY90);
    return Mat4.scale(m, m, scale);
}
export function addPlane(state, center, dirMajor, dirMinor, scale, widthSegments, heightSegments) {
    const plane = SegmentedPlane(widthSegments, heightSegments);
    MeshBuilder.addPrimitive(state, setPlaneMat(tmpPlaneMat, center, dirMajor, dirMinor, scale), plane);
}
