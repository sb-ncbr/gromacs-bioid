"use strict";
/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.StructureElementPointParams = exports.ElementPointParams = void 0;
exports.createElementPoint = createElementPoint;
exports.ElementPointVisual = ElementPointVisual;
exports.createStructureElementPoint = createStructureElementPoint;
exports.StructureElementPointVisual = StructureElementPointVisual;
const param_definition_1 = require("../../../mol-util/param-definition");
const units_visual_1 = require("../units-visual");
const points_1 = require("../../../mol-geo/geometry/points/points");
const points_builder_1 = require("../../../mol-geo/geometry/points/points-builder");
const linear_algebra_1 = require("../../../mol-math/linear-algebra");
const element_1 = require("./util/element");
const geometry_1 = require("../../../mol-math/geometry");
const complex_visual_1 = require("../complex-visual");
// avoiding namespace lookup improved performance in Chrome (Aug 2020)
const v3add = linear_algebra_1.Vec3.add;
exports.ElementPointParams = {
    ...units_visual_1.UnitsPointsParams,
    pointSizeAttenuation: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogens: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogensVariant: param_definition_1.ParamDefinition.Select('all', param_definition_1.ParamDefinition.arrayToOptions(['all', 'non-polar'])),
    traceOnly: param_definition_1.ParamDefinition.Boolean(false),
    stride: param_definition_1.ParamDefinition.Numeric(1, { min: 1, max: 100, step: 1 }),
};
// TODO size
function createElementPoint(ctx, unit, structure, theme, props, points) {
    // TODO sizeFactor
    const { child } = structure;
    const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
    if (child && !childUnit)
        return points_1.Points.createEmpty(points);
    const { stride } = props;
    const elements = unit.elements;
    const n = elements.length;
    const builder = points_builder_1.PointsBuilder.create(n, n / 10, points);
    const p = (0, linear_algebra_1.Vec3)();
    const c = unit.conformation;
    const ignore = (0, element_1.makeElementIgnoreTest)(structure, unit, props);
    const center = (0, linear_algebra_1.Vec3)();
    let count = 0;
    if ((stride && stride > 1) || ignore) {
        for (let i = 0; i < n; ++i) {
            if (stride && i % stride !== 0)
                continue;
            if (ignore && ignore(elements[i]))
                continue;
            c.invariantPosition(elements[i], p);
            v3add(center, center, p);
            count += 1;
            builder.add(p[0], p[1], p[2], i);
        }
    }
    else {
        for (let i = 0; i < n; ++i) {
            c.invariantPosition(elements[i], p);
            v3add(center, center, p);
            count += 1;
            builder.add(p[0], p[1], p[2], i);
        }
    }
    const pt = builder.getPoints();
    if (count === 0)
        return pt;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    linear_algebra_1.Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = points ? geometry_1.Sphere3D.clone(points.boundingSphere) : undefined;
    if (oldBoundingSphere && linear_algebra_1.Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 0.1) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = geometry_1.Sphere3D.expand((0, geometry_1.Sphere3D)(), (childUnit !== null && childUnit !== void 0 ? childUnit : unit).boundary.sphere, 1 * props.sizeFactor);
    }
    pt.setBoundingSphere(boundingSphere);
    return pt;
}
function ElementPointVisual(materialId) {
    return (0, units_visual_1.UnitsPointsVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.ElementPointParams),
        createGeometry: createElementPoint,
        createLocationIterator: element_1.ElementIterator.fromGroup,
        getLoci: element_1.getElementLoci,
        eachLocation: element_1.eachElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.ignoreHydrogens !== currentProps.ignoreHydrogens ||
                newProps.ignoreHydrogensVariant !== currentProps.ignoreHydrogensVariant ||
                newProps.traceOnly !== currentProps.traceOnly ||
                newProps.stride !== currentProps.stride);
        }
    }, materialId);
}
//
function createStructureElementPoint(ctx, structure, theme, props, points) {
    // TODO sizeFactor
    const { child } = structure;
    const { stride } = props;
    const { getSerialIndex } = structure.serialMapping;
    const structureElementCount = structure.elementCount;
    const builder = points_builder_1.PointsBuilder.create(structureElementCount, structureElementCount / 2, points);
    const center = (0, linear_algebra_1.Vec3)();
    let count = 0;
    for (const unit of structure.units) {
        const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
        if (child && !childUnit)
            return points_1.Points.createEmpty(points);
        const { elements, conformation: c } = unit;
        const elementCount = elements.length;
        const v = (0, linear_algebra_1.Vec3)();
        const ignore = (0, element_1.makeElementIgnoreTest)(structure, unit, props);
        if ((stride && stride > 1) || ignore) {
            for (let i = 0; i < elementCount; i++) {
                const eI = elements[i];
                if (stride && i % stride !== 0)
                    continue;
                if (ignore && ignore(eI))
                    continue;
                c.position(eI, v);
                builder.add(v[0], v[1], v[2], getSerialIndex(unit, eI));
                v3add(center, center, v);
                count += 1;
            }
        }
        else {
            for (let i = 0; i < elementCount; i++) {
                const eI = elements[i];
                c.position(eI, v);
                builder.add(v[0], v[1], v[2], getSerialIndex(unit, eI));
                v3add(center, center, v);
            }
            count += elementCount;
        }
    }
    const pt = builder.getPoints();
    if (count === 0)
        return pt;
    // re-use boundingSphere if it has not changed much
    let boundingSphere;
    linear_algebra_1.Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = points ? geometry_1.Sphere3D.clone(points.boundingSphere) : undefined;
    if (oldBoundingSphere && linear_algebra_1.Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 1.0) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = geometry_1.Sphere3D.expand((0, geometry_1.Sphere3D)(), (child !== null && child !== void 0 ? child : structure).boundary.sphere, 1 * props.sizeFactor);
    }
    pt.setBoundingSphere(boundingSphere);
    return pt;
}
exports.StructureElementPointParams = {
    ...complex_visual_1.ComplexPointsParams,
    pointSizeAttenuation: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogens: param_definition_1.ParamDefinition.Boolean(false),
    ignoreHydrogensVariant: param_definition_1.ParamDefinition.Select('all', param_definition_1.ParamDefinition.arrayToOptions(['all', 'non-polar'])),
    traceOnly: param_definition_1.ParamDefinition.Boolean(false),
    stride: param_definition_1.ParamDefinition.Numeric(1, { min: 1, max: 100, step: 1 }),
};
function StructureElementPointVisual(materialId) {
    return (0, complex_visual_1.ComplexPointsVisual)({
        defaultProps: param_definition_1.ParamDefinition.getDefaultValues(exports.StructureElementPointParams),
        createGeometry: createStructureElementPoint,
        createLocationIterator: element_1.ElementIterator.fromStructure,
        getLoci: element_1.getSerialElementLoci,
        eachLocation: element_1.eachSerialElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.ignoreHydrogens !== currentProps.ignoreHydrogens ||
                newProps.ignoreHydrogensVariant !== currentProps.ignoreHydrogensVariant ||
                newProps.traceOnly !== currentProps.traceOnly ||
                newProps.stride !== currentProps.stride);
        }
    }, materialId);
}
