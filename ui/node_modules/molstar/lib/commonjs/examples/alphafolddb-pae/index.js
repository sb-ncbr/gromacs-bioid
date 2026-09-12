"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AlphaFoldPAEExample = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
const client_1 = require("react-dom/client");
const app_1 = require("../../apps/viewer/app");
const ui_1 = require("../../extensions/model-archive/quality-assessment/pairwise/ui");
require("./index.html");
require("../../mol-plugin-ui/skin/light.scss");
class AlphaFoldPAEExample {
    async init(options) {
        this.plotContainerId = options.plotContainerId;
        this.viewer = await app_1.Viewer.create(options.pluginContainerId, {
            layoutIsExpanded: false,
            layoutShowControls: false,
            layoutShowLeftPanel: false,
            layoutShowLog: false,
        });
        return this;
    }
    async load(afId) {
        var _a, _b;
        const id = afId.trim().toUpperCase();
        const plotRoot = (0, client_1.createRoot)(document.getElementById(this.plotContainerId));
        plotRoot.render((0, jsx_runtime_1.jsx)("div", { children: "Loading..." }));
        await this.viewer.plugin.clear();
        await this.viewer.loadAlphaFoldDb(id);
        try {
            const req = await fetch(`https://alphafold.ebi.ac.uk/files/AF-${id}-F1-predicted_aligned_error_v4.json`);
            const json = await req.json();
            const model = (_b = (_a = this.viewer.plugin.managers.structure.hierarchy.current.models[0]) === null || _a === void 0 ? void 0 : _a.cell.obj) === null || _b === void 0 ? void 0 : _b.data;
            const metric = pairwiseMetricFromAlphaFoldDbJson(model, json);
            plotRoot.render((0, jsx_runtime_1.jsx)("div", { className: 'msp-plugin', style: { background: 'white' }, children: (0, jsx_runtime_1.jsx)(ui_1.MAPairwiseScorePlot, { plugin: this.viewer.plugin, pairwiseMetric: metric, model: model }) }));
        }
        catch (err) {
            plotRoot.render((0, jsx_runtime_1.jsxs)("div", { children: ["Error: ", String(err)] }));
        }
    }
}
exports.AlphaFoldPAEExample = AlphaFoldPAEExample;
function pairwiseMetricFromAlphaFoldDbJson(model, data) {
    var _a;
    if (!Array.isArray(data) || !((_a = data[0]) === null || _a === void 0 ? void 0 : _a.predicted_aligned_error))
        return undefined;
    const { residues, residueAtomSegments, atomSourceIndex } = model.atomicHierarchy;
    const sortedResidueIndices = new Array(residues._rowCount).fill(0).map((_, i) => i);
    sortedResidueIndices.sort((a, b) => {
        const idxA = atomSourceIndex.value(residueAtomSegments.offsets[a]);
        const idxB = atomSourceIndex.value(residueAtomSegments.offsets[b]);
        return idxA - idxB;
    });
    const metricData = data[0].predicted_aligned_error;
    const metric = {
        id: 0,
        name: 'AlphaFold DB PAE',
        residueRange: [0, (residues._rowCount - 1)],
        valueRange: [0, data[0].max_predicted_aligned_error],
        values: {}
    };
    for (let i = 0; i < metricData.length; i++) {
        const rA = sortedResidueIndices[i];
        if (typeof rA !== 'number')
            continue;
        const row = metricData[i];
        const xs = (metric.values[rA] = {});
        for (let j = 0; j < row.length; j++) {
            const rB = sortedResidueIndices[j];
            if (typeof rB !== 'number')
                continue;
            xs[rB] = row[j];
        }
    }
    return metric;
}
window.AlphaFoldPAEExample = new AlphaFoldPAEExample();
