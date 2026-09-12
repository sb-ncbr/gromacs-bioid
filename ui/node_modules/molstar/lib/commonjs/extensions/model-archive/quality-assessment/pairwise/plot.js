"use strict";
/**
 * Copyright (c) 2024-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.maDrawPairwiseMetricPNG = maDrawPairwiseMetricPNG;
const atomic_1 = require("../../../../mol-model/structure/model/properties/atomic");
const color_1 = require("../../../../mol-util/color");
const DefaultMetricColorRange = [0x00441B, 0xF7FCF5];
function drawMetricPNG(model, metric, colorRange, noDataColor) {
    var _a;
    const [minResidueIndex, maxResidueIndex] = metric.residueRange;
    const [minMetric, maxMetric] = metric.valueRange;
    const [minColor, maxColor] = colorRange;
    const range = maxResidueIndex - minResidueIndex + 1;
    const valueRange = maxMetric - minMetric;
    const values = metric.values;
    const canvas = document.createElement('canvas');
    canvas.width = range;
    canvas.height = range;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = color_1.Color.toStyle(noDataColor);
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const colorCache = new Map();
    const getColor = (t) => {
        const rounded = Math.round(t * 0xffff);
        if (colorCache.has(rounded)) {
            return colorCache.get(rounded);
        }
        const color = color_1.Color.interpolate(minColor, maxColor, rounded / 0xffff);
        const style = color_1.Color.toStyle(color);
        colorCache.set(rounded, style);
        return style;
    };
    for (let rA = minResidueIndex; rA <= maxResidueIndex; rA++) {
        const row = values[rA];
        if (!row)
            continue;
        for (let rB = minResidueIndex; rB <= maxResidueIndex; rB++) {
            const value = row[rB];
            if (typeof value !== 'number')
                continue;
            const x = rA - minResidueIndex;
            const y = rB - minResidueIndex;
            const t = (value - minMetric) / valueRange;
            ctx.fillStyle = getColor(t);
            ctx.fillRect(x, y, 1, 1);
            if (typeof ((_a = values[rB]) === null || _a === void 0 ? void 0 : _a[rA]) !== 'number') {
                ctx.fillRect(y, x, 1, 1);
            }
        }
    }
    const chains = [];
    const hierarchy = model.atomicHierarchy;
    const { label_asym_id } = hierarchy.chains;
    let cI = atomic_1.AtomicHierarchy.residueChainIndex(hierarchy, minResidueIndex);
    let currentChain = { startOffset: 0, endOffset: 1, label: label_asym_id.value(cI) };
    chains.push(currentChain);
    for (let i = 1; i < range; i++) {
        cI = atomic_1.AtomicHierarchy.residueChainIndex(hierarchy, (minResidueIndex + i));
        const asym_id = label_asym_id.value(cI);
        if (asym_id === currentChain.label) {
            currentChain.endOffset = i + 1;
        }
        else {
            currentChain = { startOffset: i, endOffset: i + 1, label: asym_id };
            chains.push(currentChain);
        }
    }
    return {
        model,
        metric,
        chains,
        colorRange: [color_1.Color.toStyle(colorRange[0]), color_1.Color.toStyle(colorRange[1])],
        png: canvas.toDataURL('png')
    };
}
function maDrawPairwiseMetricPNG(model, metric) {
    return drawMetricPNG(model, metric, DefaultMetricColorRange, (0, color_1.Color)(0xE2E2E2));
}
