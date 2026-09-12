/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { UnitsPointsParams, UnitsPointsVisual } from '../units-visual';
import { Points } from '../../../mol-geo/geometry/points/points';
import { PointsBuilder } from '../../../mol-geo/geometry/points/points-builder';
import { Vec3 } from '../../../mol-math/linear-algebra';
import { ElementIterator, getElementLoci, eachElement, makeElementIgnoreTest, getSerialElementLoci, eachSerialElement } from './util/element';
import { Sphere3D } from '../../../mol-math/geometry';
import { ComplexPointsParams, ComplexPointsVisual } from '../complex-visual';
// avoiding namespace lookup improved performance in Chrome (Aug 2020)
const v3add = Vec3.add;
export const ElementPointParams = {
    ...UnitsPointsParams,
    pointSizeAttenuation: PD.Boolean(false),
    ignoreHydrogens: PD.Boolean(false),
    ignoreHydrogensVariant: PD.Select('all', PD.arrayToOptions(['all', 'non-polar'])),
    traceOnly: PD.Boolean(false),
    stride: PD.Numeric(1, { min: 1, max: 100, step: 1 }),
};
// TODO size
export function createElementPoint(ctx, unit, structure, theme, props, points) {
    // TODO sizeFactor
    const { child } = structure;
    const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
    if (child && !childUnit)
        return Points.createEmpty(points);
    const { stride } = props;
    const elements = unit.elements;
    const n = elements.length;
    const builder = PointsBuilder.create(n, n / 10, points);
    const p = Vec3();
    const c = unit.conformation;
    const ignore = makeElementIgnoreTest(structure, unit, props);
    const center = Vec3();
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
    Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = points ? Sphere3D.clone(points.boundingSphere) : undefined;
    if (oldBoundingSphere && Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 0.1) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = Sphere3D.expand(Sphere3D(), (childUnit !== null && childUnit !== void 0 ? childUnit : unit).boundary.sphere, 1 * props.sizeFactor);
    }
    pt.setBoundingSphere(boundingSphere);
    return pt;
}
export function ElementPointVisual(materialId) {
    return UnitsPointsVisual({
        defaultProps: PD.getDefaultValues(ElementPointParams),
        createGeometry: createElementPoint,
        createLocationIterator: ElementIterator.fromGroup,
        getLoci: getElementLoci,
        eachLocation: eachElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.ignoreHydrogens !== currentProps.ignoreHydrogens ||
                newProps.ignoreHydrogensVariant !== currentProps.ignoreHydrogensVariant ||
                newProps.traceOnly !== currentProps.traceOnly ||
                newProps.stride !== currentProps.stride);
        }
    }, materialId);
}
//
export function createStructureElementPoint(ctx, structure, theme, props, points) {
    // TODO sizeFactor
    const { child } = structure;
    const { stride } = props;
    const { getSerialIndex } = structure.serialMapping;
    const structureElementCount = structure.elementCount;
    const builder = PointsBuilder.create(structureElementCount, structureElementCount / 2, points);
    const center = Vec3();
    let count = 0;
    for (const unit of structure.units) {
        const childUnit = child === null || child === void 0 ? void 0 : child.unitMap.get(unit.id);
        if (child && !childUnit)
            return Points.createEmpty(points);
        const { elements, conformation: c } = unit;
        const elementCount = elements.length;
        const v = Vec3();
        const ignore = makeElementIgnoreTest(structure, unit, props);
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
    Vec3.scale(center, center, 1 / count);
    const oldBoundingSphere = points ? Sphere3D.clone(points.boundingSphere) : undefined;
    if (oldBoundingSphere && Vec3.distance(center, oldBoundingSphere.center) / oldBoundingSphere.radius < 1.0) {
        boundingSphere = oldBoundingSphere;
    }
    else {
        boundingSphere = Sphere3D.expand(Sphere3D(), (child !== null && child !== void 0 ? child : structure).boundary.sphere, 1 * props.sizeFactor);
    }
    pt.setBoundingSphere(boundingSphere);
    return pt;
}
export const StructureElementPointParams = {
    ...ComplexPointsParams,
    pointSizeAttenuation: PD.Boolean(false),
    ignoreHydrogens: PD.Boolean(false),
    ignoreHydrogensVariant: PD.Select('all', PD.arrayToOptions(['all', 'non-polar'])),
    traceOnly: PD.Boolean(false),
    stride: PD.Numeric(1, { min: 1, max: 100, step: 1 }),
};
export function StructureElementPointVisual(materialId) {
    return ComplexPointsVisual({
        defaultProps: PD.getDefaultValues(StructureElementPointParams),
        createGeometry: createStructureElementPoint,
        createLocationIterator: ElementIterator.fromStructure,
        getLoci: getSerialElementLoci,
        eachLocation: eachSerialElement,
        setUpdateState: (state, newProps, currentProps) => {
            state.createGeometry = (newProps.ignoreHydrogens !== currentProps.ignoreHydrogens ||
                newProps.ignoreHydrogensVariant !== currentProps.ignoreHydrogensVariant ||
                newProps.traceOnly !== currentProps.traceOnly ||
                newProps.stride !== currentProps.stride);
        }
    }, materialId);
}
