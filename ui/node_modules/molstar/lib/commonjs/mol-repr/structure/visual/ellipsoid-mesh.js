"use strict";
/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.StructureEllipsoidMeshParams = exports.EllipsoidMeshParams = void 0;
exports.createEllipsoidMesh = createEllipsoidMesh;
exports.EllipsoidMeshVisual = EllipsoidMeshVisual;
exports.createStructureEllipsoidMesh = createStructureEllipsoidMesh;
exports.StructureEllipsoidMeshVisual = StructureEllipsoidMeshVisual;
const param_definition_1 = require("../../../mol-util/param-definition");
const units_visual_1 = require("../../../mol-repr/structure/units-visual");
const element_1 = require("../../../mol-repr/structure/visual/util/element");
const structure_1 = require("../../../mol-model/structure");
const mesh_1 = require("../../../mol-geo/geometry/mesh/mesh");
const sphere_1 = require("../../../mol-geo/primitive/sphere");
const mesh_builder_1 = require("../../../mol-geo/geometry/mesh/mesh-builder");
const linear_algebra_1 = require("../../../mol-math/linear-algebra");
const ellipsoid_1 = require("../../../mol-geo/geometry/mesh/builder/ellipsoid");
const anisotropic_1 = require("../../../mol-model-formats/structure/property/anisotropic");
const common_1 = require("../../../mol-math/linear-algebra/3d/common");
const sphere_2 = require("../../../mol-geo/geometry/mesh/builder/sphere");
const geometry_1 = require("../../../mol-math/geometry");
const base_1 = require("../../../mol-geo/geometry/base");
const complex_visual_1 = require("../complex-visual");
// avoiding namespace lookup improved performance in Chrome (Aug 2020)
const v3add = linear_algebra_1.Vec3.add;
function createEllipsoidMesh(ctx, unit, structure, theme, props, mesh) {
    const { child } = structure;
    const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
    if (child && !childUnit)
        return mesh_1.Mesh.createEmpty(mesh);
    const { detail, sizeFactor } = props;
    const { elements, model } = unit;
    const elementCount = elements.length;
    const vertexCount = elementCount * (0, sphere_1.sphereVertexCount)(detail);
    const builderState = mesh_builder_1.MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const atomSiteAnisotrop = anisotropic_1.AtomSiteAnisotrop.Provider.get(model);
    if (!atomSiteAnisotrop)
        return mesh_1.Mesh.createEmpty(mesh);
    const v = (0, linear_algebra_1.Vec3)();
    const mat = (0, linear_algebra_1.Mat3)();
    const eigvals = (0, linear_algebra_1.Vec3)();
    const eigvec1 = (0, linear_algebra_1.Vec3)();
    const eigvec2 = (0, linear_algebra_1.Vec3)();
    const { elementToAnsiotrop, data } = atomSiteAnisotrop;
    const { U } = data;
    const space = data._schema.U.space;
    const c = unit.conformation;
    const l = structure_1.StructureElement.Location.create(structure);
    l.unit = unit;
    const ignore = (0, element_1.makeElementIgnoreTest)(structure, unit, props);
    const center = (0, linear_algebra_1.Vec3)();
    let count = 0;
    for (let i = 0; i < elementCount; i++) {
        const ei = elements[i];
        const ai = elementToAnsiotrop[ei];
        if (ai === -1)
            continue;
        if (ignore && ignore(elements[i]))
            continue;
        l.element = ei;
        c.invariantPosition(ei, v);
        v3add(center, center, v);
        count += 1;
        builderState.currentGroup = i;
        linear_algebra_1.Tensor.toMat3(mat, space, U.value(ai));
        linear_algebra_1.Mat3.symmtricFromLower(mat, mat);
        linear_algebra_1.Mat3.symmetricEigenvalues(eigvals, mat);
        linear_algebra_1.Mat3.eigenvector(eigvec1, mat, eigvals[1]);
        linear_algebra_1.Mat3.eigenvector(eigvec2, mat, eigvals[2]);
        for (let j = 0; j < 3; ++j) {
            // show 50% probability surface, needs sqrt as U matrix is in angstrom-squared
            // take abs of eigenvalue to avoid reflection
            // multiply by given size-factor
            eigvals[j] = sizeFactor * 1.5958 * Math.sqrt(Math.abs(eigvals[j]));
        }
        if ((0, common_1.equalEps)(eigvals[0], eigvals[1], linear_algebra_1.EPSILON) && (0, common_1.equalEps)(eigvals[1], eigvals[2], linear_algebra_1.EPSILON)) {
            (0, sphere_2.addSphere)(builderState, v, eigvals[0], detail);
        }
        else {
            (0, ellipsoid_1.addEllipsoid)(builderState, v, eigvec2, eigvec1, eigvals, detail);
        }
    }
    const m = mesh_builder_1.MeshBuilder.getMesh(builderState);
    if (count === 0)
        return m;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    linear_algebra_1.Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = mesh ? geometry_1.Sphere3D.clone(mesh.boundingSphere) : undefined;
    if (oldBoundingSphere && linear_algebra_1.Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 0.1) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = geometry_1.Sphere3D.expand((0, geometry_1.Sphere3D)(), (childUnit !== null && childUnit !== void 0 ? childUnit : unit).boundary.sphere, 1 * sizeFactor * 2);
    }
    m.setBoundingSphere(boundingSphere);
    return m;
}
exports.EllipsoidMeshParams = {
    ...units_visual_1.UnitsMeshParams,
    sizeFactor: param_definition_1.ParamDefinition.Numeric(1, { min: 0, max: 10, step: 0.1 }),
    detail: param_definition_1.ParamDefinition.Numeric(0, { min: 0, max: 3, step: 1 }, base_1.BaseGeometry.CustomQualityParamInfo),
    ignoreHydrogens: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogensVariant: param_definition_1.ParamDefinition.Select('all', param_definition_1.ParamDefinition.arrayToOptions(['all', 'non-polar'])),
    traceOnly: param_definition_1.ParamDefinition.Boolean(false),
};
function EllipsoidMeshVisual(materialId) {
    return (0, units_visual_1.UnitsMeshVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.EllipsoidMeshParams),
        createGeometry: createEllipsoidMesh,
        createLocationIterator: element_1.ElementIterator.fromGroup,
        getLoci: element_1.getElementLoci,
        eachLocation: element_1.eachElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail ||
                newProps.ignoreHydrogens !== currentProps.ignoreHydrogens);
        }
    }, materialId);
}
//
function createStructureEllipsoidMesh(ctx, structure, theme, props, mesh) {
    const { child } = structure;
    const { detail, sizeFactor } = props;
    const { getSerialIndex } = structure.serialMapping;
    const structureElementCount = structure.elementCount;
    const vertexCount = structureElementCount * (0, sphere_1.sphereVertexCount)(detail);
    const builderState = mesh_builder_1.MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const v = (0, linear_algebra_1.Vec3)();
    const mat = (0, linear_algebra_1.Mat3)();
    const eigvals = (0, linear_algebra_1.Vec3)();
    const eigvec1 = (0, linear_algebra_1.Vec3)();
    const eigvec2 = (0, linear_algebra_1.Vec3)();
    const center = (0, linear_algebra_1.Vec3)();
    let count = 0;
    for (const unit of structure.units) {
        const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
        if (child && !childUnit)
            return mesh_1.Mesh.createEmpty(mesh);
        const { elements, model } = unit;
        const elementCount = elements.length;
        const atomSiteAnisotrop = anisotropic_1.AtomSiteAnisotrop.Provider.get(model);
        if (!atomSiteAnisotrop)
            return mesh_1.Mesh.createEmpty(mesh);
        const ignore = (0, element_1.makeElementIgnoreTest)(structure, unit, props);
        const { elementToAnsiotrop, data } = atomSiteAnisotrop;
        const { U } = data;
        const space = data._schema.U.space;
        const c = unit.conformation;
        const l = structure_1.StructureElement.Location.create(structure);
        l.unit = unit;
        // for (let i = 0 as StructureElement.UnitIndex; i < elementCount; i++) {
        //     if (ignore && ignore(elements[i])) continue;
        //     if (lone && Unit.isAtomic(unit) && hasUnitVisibleBonds(unit, props) && bondCount(structure, unit, i) !== 0) continue;
        //     c.position(elements[i], p);
        //     v3add(center, center, p);
        //     count += 1;
        //     const si = getSerialIndex(unit, elements[i]);
        //     v3scaleAndAdd(s, p, v3unitX, r);
        //     v3scaleAndAdd(e, p, v3unitX, -r);
        //     builder.add(s[0], s[1], s[2], e[0], e[1], e[2], si);
        //     v3scaleAndAdd(s, p, v3unitY, r);
        //     v3scaleAndAdd(e, p, v3unitY, -r);
        //     builder.add(s[0], s[1], s[2], e[0], e[1], e[2], si);
        //     v3scaleAndAdd(s, p, v3unitZ, r);
        //     v3scaleAndAdd(e, p, v3unitZ, -r);
        //     builder.add(s[0], s[1], s[2], e[0], e[1], e[2], si);
        // }
        for (let i = 0; i < elementCount; i++) {
            const ei = elements[i];
            const ai = elementToAnsiotrop[ei];
            if (ai === -1)
                continue;
            if (ignore && ignore(elements[i]))
                continue;
            l.element = ei;
            c.position(ei, v);
            v3add(center, center, v);
            count += 1;
            builderState.currentGroup = getSerialIndex(unit, elements[i]);
            linear_algebra_1.Tensor.toMat3(mat, space, U.value(ai));
            linear_algebra_1.Mat3.symmtricFromLower(mat, mat);
            linear_algebra_1.Mat3.symmetricEigenvalues(eigvals, mat);
            linear_algebra_1.Mat3.eigenvector(eigvec1, mat, eigvals[1]);
            linear_algebra_1.Mat3.eigenvector(eigvec2, mat, eigvals[2]);
            for (let j = 0; j < 3; ++j) {
                // show 50% probability surface, needs sqrt as U matrix is in angstrom-squared
                // take abs of eigenvalue to avoid reflection
                // multiply by given size-factor
                eigvals[j] = sizeFactor * 1.5958 * Math.sqrt(Math.abs(eigvals[j]));
            }
            if ((0, common_1.equalEps)(eigvals[0], eigvals[1], linear_algebra_1.EPSILON) && (0, common_1.equalEps)(eigvals[1], eigvals[2], linear_algebra_1.EPSILON)) {
                (0, sphere_2.addSphere)(builderState, v, eigvals[0], detail);
            }
            else {
                (0, ellipsoid_1.addEllipsoid)(builderState, v, eigvec2, eigvec1, eigvals, detail);
            }
        }
    }
    const m = mesh_builder_1.MeshBuilder.getMesh(builderState);
    if (count === 0)
        return m;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    linear_algebra_1.Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = mesh ? geometry_1.Sphere3D.clone(mesh.boundingSphere) : undefined;
    if (oldBoundingSphere && linear_algebra_1.Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 1.0) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = geometry_1.Sphere3D.expand((0, geometry_1.Sphere3D)(), (child !== null && child !== void 0 ? child : structure).boundary.sphere, 1 * sizeFactor * 2);
    }
    m.setBoundingSphere(boundingSphere);
    return m;
}
exports.StructureEllipsoidMeshParams = {
    ...complex_visual_1.ComplexMeshParams,
    sizeFactor: param_definition_1.ParamDefinition.Numeric(1, { min: 0, max: 10, step: 0.1 }),
    detail: param_definition_1.ParamDefinition.Numeric(0, { min: 0, max: 3, step: 1 }, base_1.BaseGeometry.CustomQualityParamInfo),
    ignoreHydrogens: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogensVariant: param_definition_1.ParamDefinition.Select('all', param_definition_1.ParamDefinition.arrayToOptions(['all', 'non-polar'])),
    traceOnly: param_definition_1.ParamDefinition.Boolean(false),
};
function StructureEllipsoidMeshVisual(materialId) {
    return (0, complex_visual_1.ComplexMeshVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.StructureEllipsoidMeshParams),
        createGeometry: createStructureEllipsoidMesh,
        createLocationIterator: element_1.ElementIterator.fromStructure,
        getLoci: element_1.getSerialElementLoci,
        eachLocation: element_1.eachSerialElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail ||
                newProps.ignoreHydrogens !== currentProps.ignoreHydrogens);
        }
    }, materialId);
}
