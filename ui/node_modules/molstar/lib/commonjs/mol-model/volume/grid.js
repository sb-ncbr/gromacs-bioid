"use strict";
/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.Grid = void 0;
const geometry_1 = require("../../mol-math/geometry");
const linear_algebra_1 = require("../../mol-math/linear-algebra");
const histogram_1 = require("../../mol-math/histogram");
const interpolate_1 = require("../../mol-math/interpolate");
var Grid;
(function (Grid) {
    Grid.One = {
        transform: { kind: 'matrix', matrix: linear_algebra_1.Mat4.identity() },
        cells: linear_algebra_1.Tensor.create(linear_algebra_1.Tensor.Space([1, 1, 1], [0, 1, 2]), linear_algebra_1.Tensor.Data1([0])),
        stats: { min: 0, max: 0, mean: 0, sigma: 0 },
    };
    const _scale = linear_algebra_1.Mat4.zero(), _translate = linear_algebra_1.Mat4.zero();
    function getGridToCartesianTransform(grid) {
        if (grid.transform.kind === 'matrix') {
            return linear_algebra_1.Mat4.copy((0, linear_algebra_1.Mat4)(), grid.transform.matrix);
        }
        if (grid.transform.kind === 'spacegroup') {
            const { cells: { space } } = grid;
            const scale = linear_algebra_1.Mat4.fromScaling(_scale, linear_algebra_1.Vec3.div(linear_algebra_1.Vec3.zero(), geometry_1.Box3D.size(linear_algebra_1.Vec3.zero(), grid.transform.fractionalBox), linear_algebra_1.Vec3.ofArray(space.dimensions)));
            const translate = linear_algebra_1.Mat4.fromTranslation(_translate, grid.transform.fractionalBox.min);
            return linear_algebra_1.Mat4.mul3(linear_algebra_1.Mat4.zero(), grid.transform.cell.fromFractional, translate, scale);
        }
        return linear_algebra_1.Mat4.identity();
    }
    Grid.getGridToCartesianTransform = getGridToCartesianTransform;
    function areEquivalent(gridA, gridB) {
        return gridA === gridB;
    }
    Grid.areEquivalent = areEquivalent;
    function isEmpty(grid) {
        return grid.cells.data.length === 0;
    }
    Grid.isEmpty = isEmpty;
    function getBoundingSphere(grid, boundingSphere) {
        if (!boundingSphere)
            boundingSphere = (0, geometry_1.Sphere3D)();
        const dimensions = grid.cells.space.dimensions;
        const transform = Grid.getGridToCartesianTransform(grid);
        return geometry_1.Sphere3D.fromDimensionsAndTransform(boundingSphere, dimensions, transform);
    }
    Grid.getBoundingSphere = getBoundingSphere;
    /**
     * Compute histogram with given bin count.
     * Cached on the Grid object.
     */
    function getHistogram(grid, binCount) {
        let histograms = grid._historams;
        if (!histograms) {
            histograms = grid._historams = {};
        }
        if (!histograms[binCount]) {
            histograms[binCount] = (0, histogram_1.calculateHistogram)(grid.cells.data, binCount, { min: grid.stats.min, max: grid.stats.max });
        }
        return histograms[binCount];
    }
    Grid.getHistogram = getHistogram;
    function makeGetTrilinearlyInterpolated(grid, transform) {
        const cartnToGrid = Grid.getGridToCartesianTransform(grid);
        linear_algebra_1.Mat4.invert(cartnToGrid, cartnToGrid);
        const gridCoords = (0, linear_algebra_1.Vec3)();
        const { stats } = grid;
        const { dimensions, get } = grid.cells.space;
        const data = grid.cells.data;
        const [mi, mj, mk] = dimensions;
        return function getTrilinearlyInterpolated(position) {
            linear_algebra_1.Vec3.copy(gridCoords, position);
            linear_algebra_1.Vec3.transformMat4(gridCoords, gridCoords, cartnToGrid);
            const i = Math.trunc(gridCoords[0]);
            const j = Math.trunc(gridCoords[1]);
            const k = Math.trunc(gridCoords[2]);
            if (i < 0 || i >= mi || j < 0 || j >= mj || k < 0 || k >= mk) {
                return Number.NaN;
            }
            const u = gridCoords[0] - i;
            const v = gridCoords[1] - j;
            const w = gridCoords[2] - k;
            // Tri-linear interpolation for the value
            const ii = Math.min(i + 1, mi - 1);
            const jj = Math.min(j + 1, mj - 1);
            const kk = Math.min(k + 1, mk - 1);
            let a = get(data, i, j, k);
            let b = get(data, ii, j, k);
            let c = get(data, i, jj, k);
            let d = get(data, ii, jj, k);
            const x = (0, interpolate_1.lerp)((0, interpolate_1.lerp)(a, b, u), (0, interpolate_1.lerp)(c, d, u), v);
            a = get(data, i, j, kk);
            b = get(data, ii, j, kk);
            c = get(data, i, jj, kk);
            d = get(data, ii, jj, kk);
            const y = (0, interpolate_1.lerp)((0, interpolate_1.lerp)(a, b, u), (0, interpolate_1.lerp)(c, d, u), v);
            const value = (0, interpolate_1.lerp)(x, y, w);
            if (transform === 'relative') {
                return (value - stats.mean) / stats.sigma;
            }
            else {
                return value;
            }
        };
    }
    Grid.makeGetTrilinearlyInterpolated = makeGetTrilinearlyInterpolated;
})(Grid || (exports.Grid = Grid = {}));
