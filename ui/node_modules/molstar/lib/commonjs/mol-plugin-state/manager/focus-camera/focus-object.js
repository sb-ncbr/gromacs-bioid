"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getFocusSnapshot = getFocusSnapshot;
exports.getCellBoundingSphere = getCellBoundingSphere;
exports.getPluginBoundingSphere = getPluginBoundingSphere;
const geometry_1 = require("../../../mol-math/geometry");
const boundary_helper_1 = require("../../../mol-math/geometry/boundary-helper");
const linear_algebra_1 = require("../../../mol-math/linear-algebra");
const loci_1 = require("../../../mol-model/loci");
const structure_1 = require("../../../mol-model/structure");
const objects_1 = require("../../objects");
/** Return camera snapshot focused on a plugin state object cell (if `targetRef` is defined)
 * or on the whole scene (if `targetRef` is undefined).
 * If `direction` and `up` are not provided, use current camera orientation. */
function getFocusSnapshot(plugin, options) {
    var _a, _b;
    if (!plugin.canvas3d)
        return undefined;
    const targetSpheres = (_a = options.targets) === null || _a === void 0 ? void 0 : _a.map(target => {
        var _a, _b, _c;
        const bounding = (target.targetRef !== undefined) ? getCellBoundingSphere(plugin, target.targetRef) : getPluginBoundingSphere(plugin);
        if (!bounding)
            return undefined;
        const radius = (_a = target.radius) !== null && _a !== void 0 ? _a : bounding.radius * ((_b = target.radiusFactor) !== null && _b !== void 0 ? _b : 1) + ((_c = target.extraRadius) !== null && _c !== void 0 ? _c : 0);
        return geometry_1.Sphere3D.create(bounding.center, radius);
    }).filter(sphere => sphere !== undefined);
    const mergedSphere = (targetSpheres && targetSpheres.length > 0) ? boundingSphereOfSpheres(targetSpheres) : getPluginBoundingSphere(plugin);
    return snapshotFromSphereAndDirections(plugin.canvas3d.camera, {
        center: mergedSphere.center,
        radius: Math.max(mergedSphere.radius, (_b = options.minRadius) !== null && _b !== void 0 ? _b : 0),
        up: options.up,
        direction: options.direction,
    });
}
const _tmpVec = (0, linear_algebra_1.Vec3)();
/** Return camera snapshot for focusing a sphere with given `center` and `radius`,
 * while ensuring given view `direction` (aligns with vector position->target)
 * and `up` (aligns with screen Y axis). */
function snapshotFromSphereAndDirections(camera, options) {
    var _a, _b;
    // This might seem to repeat `plugin.canvas3d.camera.getFocus` but avoid flipping
    const target = options.center;
    const radius = Math.max(options.radius, 0.01);
    const direction = (_a = options.direction) !== null && _a !== void 0 ? _a : linear_algebra_1.Vec3.sub((0, linear_algebra_1.Vec3)(), camera.target, camera.position);
    const up = linear_algebra_1.Vec3.orthogonalize((0, linear_algebra_1.Vec3)(), direction, (_b = options.up) !== null && _b !== void 0 ? _b : camera.up);
    const distance = camera.getTargetDistance(radius);
    const deltaDirection = linear_algebra_1.Vec3.setMagnitude(_tmpVec, direction, distance);
    const position = linear_algebra_1.Vec3.sub((0, linear_algebra_1.Vec3)(), target, deltaDirection);
    return { target, position, up, radius };
}
/** Return the bounding sphere of a plugin state object cell */
function getCellBoundingSphere(plugin, cellRef) {
    const spheres = collectCellBoundingSpheres([], plugin, cellRef);
    if (spheres.length === 0)
        return undefined;
    if (spheres.length === 1)
        return spheres[0];
    return boundingSphereOfSpheres(spheres);
}
/** Push bounding spheres within cell `cellRef` to `out`. If a cell does not define bounding spheres, collect bounding spheres from subtree. */
function collectCellBoundingSpheres(out, plugin, cellRef) {
    const cell = plugin.state.data.cells.get(cellRef);
    const spheres = getStateObjectBoundingSpheres(cell === null || cell === void 0 ? void 0 : cell.obj);
    if (spheres) {
        out.push(...spheres);
    }
    else {
        const children = plugin.state.data.tree.children.get(cellRef);
        children.forEach(child => collectCellBoundingSpheres(out, plugin, child));
    }
    return out;
}
/** Return a set of bounding spheres of a plugin state object. Return `undefined` if this plugin state object type does not define bounding spheres. */
function getStateObjectBoundingSpheres(obj) {
    if (!obj)
        return undefined;
    if (!obj.data) {
        console.warn('Focus: no data');
        return undefined;
    }
    if (obj.data instanceof structure_1.Structure) {
        const sphere = loci_1.Loci.getBoundingSphere(structure_1.Structure.Loci(obj.data));
        return sphere ? [sphere] : [];
    }
    else if (objects_1.PluginStateObject.isRepresentation3D(obj)) {
        const out = [];
        for (const renderObject of obj.data.repr.renderObjects) {
            const sphere = renderObject.values.boundingSphere.ref.value;
            if (sphere.radius > 0)
                out.push(sphere);
        }
        return out;
    }
    return undefined;
}
/** Return the bounding sphere of the whole visible scene. */
function getPluginBoundingSphere(plugin) {
    const renderObjects = getRenderObjects(plugin, false);
    const spheres = renderObjects.map(r => r.values.boundingSphere.ref.value).filter(sphere => sphere.radius > 0);
    return boundingSphereOfSpheres(spheres);
}
function getRenderObjects(plugin, includeHidden) {
    let reprCells = Array.from(plugin.state.data.cells.values()).filter(cell => cell.obj && objects_1.PluginStateObject.isRepresentation3D(cell.obj));
    if (!includeHidden)
        reprCells = reprCells.filter(cell => !cell.state.isHidden);
    const renderables = reprCells.flatMap(cell => cell.obj.data.repr.renderObjects);
    return renderables;
}
let boundaryHelper = undefined;
function boundingSphereOfSpheres(spheres) {
    boundaryHelper !== null && boundaryHelper !== void 0 ? boundaryHelper : (boundaryHelper = new boundary_helper_1.BoundaryHelper('98'));
    boundaryHelper.reset();
    for (const s of spheres)
        boundaryHelper.includeSphere(s);
    boundaryHelper.finishedIncludeStep();
    for (const s of spheres)
        boundaryHelper.radiusSphere(s);
    return boundaryHelper.getSphere();
}
