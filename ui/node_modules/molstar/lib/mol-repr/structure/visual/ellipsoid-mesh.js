/**
 * Copyright (c) 2019-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { UnitsMeshParams, UnitsMeshVisual } from '../../../mol-repr/structure/units-visual';
import { ElementIterator, getElementLoci, eachElement, getSerialElementLoci, eachSerialElement, makeElementIgnoreTest } from '../../../mol-repr/structure/visual/util/element';
import { StructureElement } from '../../../mol-model/structure';
import { Mesh } from '../../../mol-geo/geometry/mesh/mesh';
import { sphereVertexCount } from '../../../mol-geo/primitive/sphere';
import { MeshBuilder } from '../../../mol-geo/geometry/mesh/mesh-builder';
import { Vec3, Mat3, Tensor, EPSILON } from '../../../mol-math/linear-algebra';
import { addEllipsoid } from '../../../mol-geo/geometry/mesh/builder/ellipsoid';
import { AtomSiteAnisotrop } from '../../../mol-model-formats/structure/property/anisotropic';
import { equalEps } from '../../../mol-math/linear-algebra/3d/common';
import { addSphere } from '../../../mol-geo/geometry/mesh/builder/sphere';
import { Sphere3D } from '../../../mol-math/geometry';
import { BaseGeometry } from '../../../mol-geo/geometry/base';
import { ComplexMeshParams, ComplexMeshVisual } from '../complex-visual';
// avoiding namespace lookup improved performance in Chrome (Aug 2020)
const v3add = Vec3.add;
export function createEllipsoidMesh(ctx, unit, structure, theme, props, mesh) {
    const { child } = structure;
    const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
    if (child && !childUnit)
        return Mesh.createEmpty(mesh);
    const { detail, sizeFactor } = props;
    const { elements, model } = unit;
    const elementCount = elements.length;
    const vertexCount = elementCount * sphereVertexCount(detail);
    const builderState = MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const atomSiteAnisotrop = AtomSiteAnisotrop.Provider.get(model);
    if (!atomSiteAnisotrop)
        return Mesh.createEmpty(mesh);
    const v = Vec3();
    const mat = Mat3();
    const eigvals = Vec3();
    const eigvec1 = Vec3();
    const eigvec2 = Vec3();
    const { elementToAnsiotrop, data } = atomSiteAnisotrop;
    const { U } = data;
    const space = data._schema.U.space;
    const c = unit.conformation;
    const l = StructureElement.Location.create(structure);
    l.unit = unit;
    const ignore = makeElementIgnoreTest(structure, unit, props);
    const center = Vec3();
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
        Tensor.toMat3(mat, space, U.value(ai));
        Mat3.symmtricFromLower(mat, mat);
        Mat3.symmetricEigenvalues(eigvals, mat);
        Mat3.eigenvector(eigvec1, mat, eigvals[1]);
        Mat3.eigenvector(eigvec2, mat, eigvals[2]);
        for (let j = 0; j < 3; ++j) {
            // show 50% probability surface, needs sqrt as U matrix is in angstrom-squared
            // take abs of eigenvalue to avoid reflection
            // multiply by given size-factor
            eigvals[j] = sizeFactor * 1.5958 * Math.sqrt(Math.abs(eigvals[j]));
        }
        if (equalEps(eigvals[0], eigvals[1], EPSILON) && equalEps(eigvals[1], eigvals[2], EPSILON)) {
            addSphere(builderState, v, eigvals[0], detail);
        }
        else {
            addEllipsoid(builderState, v, eigvec2, eigvec1, eigvals, detail);
        }
    }
    const m = MeshBuilder.getMesh(builderState);
    if (count === 0)
        return m;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = mesh ? Sphere3D.clone(mesh.boundingSphere) : undefined;
    if (oldBoundingSphere && Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 0.1) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = Sphere3D.expand(Sphere3D(), (childUnit !== null && childUnit !== void 0 ? childUnit : unit).boundary.sphere, 1 * sizeFactor * 2);
    }
    m.setBoundingSphere(boundingSphere);
    return m;
}
export const EllipsoidMeshParams = {
    ...UnitsMeshParams,
    sizeFactor: PD.Numeric(1, { min: 0, max: 10, step: 0.1 }),
    detail: PD.Numeric(0, { min: 0, max: 3, step: 1 }, BaseGeometry.CustomQualityParamInfo),
    ignoreHydrogens: PD.Boolean(false),
    ignoreHydrogensVariant: PD.Select('all', PD.arrayToOptions(['all', 'non-polar'])),
    traceOnly: PD.Boolean(false),
};
export function EllipsoidMeshVisual(materialId) {
    return UnitsMeshVisual({
        defaultProps: PD.getDefaultValues(EllipsoidMeshParams),
        createGeometry: createEllipsoidMesh,
        createLocationIterator: ElementIterator.fromGroup,
        getLoci: getElementLoci,
        eachLocation: eachElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail ||
                newProps.ignoreHydrogens !== currentProps.ignoreHydrogens);
        }
    }, materialId);
}
//
export function createStructureEllipsoidMesh(ctx, structure, theme, props, mesh) {
    const { child } = structure;
    const { detail, sizeFactor } = props;
    const { getSerialIndex } = structure.serialMapping;
    const structureElementCount = structure.elementCount;
    const vertexCount = structureElementCount * sphereVertexCount(detail);
    const builderState = MeshBuilder.createState(vertexCount, vertexCount / 2, mesh);
    const v = Vec3();
    const mat = Mat3();
    const eigvals = Vec3();
    const eigvec1 = Vec3();
    const eigvec2 = Vec3();
    const center = Vec3();
    let count = 0;
    for (const unit of structure.units) {
        const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
        if (child && !childUnit)
            return Mesh.createEmpty(mesh);
        const { elements, model } = unit;
        const elementCount = elements.length;
        const atomSiteAnisotrop = AtomSiteAnisotrop.Provider.get(model);
        if (!atomSiteAnisotrop)
            return Mesh.createEmpty(mesh);
        const ignore = makeElementIgnoreTest(structure, unit, props);
        const { elementToAnsiotrop, data } = atomSiteAnisotrop;
        const { U } = data;
        const space = data._schema.U.space;
        const c = unit.conformation;
        const l = StructureElement.Location.create(structure);
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
            Tensor.toMat3(mat, space, U.value(ai));
            Mat3.symmtricFromLower(mat, mat);
            Mat3.symmetricEigenvalues(eigvals, mat);
            Mat3.eigenvector(eigvec1, mat, eigvals[1]);
            Mat3.eigenvector(eigvec2, mat, eigvals[2]);
            for (let j = 0; j < 3; ++j) {
                // show 50% probability surface, needs sqrt as U matrix is in angstrom-squared
                // take abs of eigenvalue to avoid reflection
                // multiply by given size-factor
                eigvals[j] = sizeFactor * 1.5958 * Math.sqrt(Math.abs(eigvals[j]));
            }
            if (equalEps(eigvals[0], eigvals[1], EPSILON) && equalEps(eigvals[1], eigvals[2], EPSILON)) {
                addSphere(builderState, v, eigvals[0], detail);
            }
            else {
                addEllipsoid(builderState, v, eigvec2, eigvec1, eigvals, detail);
            }
        }
    }
    const m = MeshBuilder.getMesh(builderState);
    if (count === 0)
        return m;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = mesh ? Sphere3D.clone(mesh.boundingSphere) : undefined;
    if (oldBoundingSphere && Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 1.0) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = Sphere3D.expand(Sphere3D(), (child !== null && child !== void 0 ? child : structure).boundary.sphere, 1 * sizeFactor * 2);
    }
    m.setBoundingSphere(boundingSphere);
    return m;
}
export const StructureEllipsoidMeshParams = {
    ...ComplexMeshParams,
    sizeFactor: PD.Numeric(1, { min: 0, max: 10, step: 0.1 }),
    detail: PD.Numeric(0, { min: 0, max: 3, step: 1 }, BaseGeometry.CustomQualityParamInfo),
    ignoreHydrogens: PD.Boolean(false),
    ignoreHydrogensVariant: PD.Select('all', PD.arrayToOptions(['all', 'non-polar'])),
    traceOnly: PD.Boolean(false),
};
export function StructureEllipsoidMeshVisual(materialId) {
    return ComplexMeshVisual({
        defaultProps: PD.getDefaultValues(StructureEllipsoidMeshParams),
        createGeometry: createStructureEllipsoidMesh,
        createLocationIterator: ElementIterator.fromStructure,
        getLoci: getSerialElementLoci,
        eachLocation: eachSerialElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.sizeFactor !== currentProps.sizeFactor ||
                newProps.detail !== currentProps.detail ||
                newProps.ignoreHydrogens !== currentProps.ignoreHydrogens);
        }
    }, materialId);
}
