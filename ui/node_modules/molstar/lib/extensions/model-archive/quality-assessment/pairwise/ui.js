import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Fragment, memo, useEffect, useRef } from 'react';
import { BehaviorSubject, combineLatest, distinctUntilChanged, throttleTime } from 'rxjs';
import { clamp } from '../../../../mol-math/interpolate';
import { StructureElement, StructureProperties, StructureQuery } from '../../../../mol-model/structure';
import { AtomicHierarchy } from '../../../../mol-model/structure/model/properties/atomic';
import { atoms } from '../../../../mol-model/structure/query/queries/generators';
import { PluginStateObject } from '../../../../mol-plugin-state/objects';
import { OverpaintStructureRepresentation3DFromBundle } from '../../../../mol-plugin-state/transforms/representation';
import { CollapsableControls } from '../../../../mol-plugin-ui/base';
import { ScatterPlotSvg } from '../../../../mol-plugin-ui/controls/icons';
import { ParameterControls } from '../../../../mol-plugin-ui/controls/parameters';
import { useBehavior } from '../../../../mol-plugin-ui/hooks/use-behavior';
import { round } from '../../../../mol-util';
import { Color } from '../../../../mol-util/color';
import { ParamDefinition as PD } from '../../../../mol-util/param-definition';
import { SingleAsyncQueue } from '../../../../mol-util/single-async-queue';
import { QualityAssessment } from '../prop';
import { maDrawPairwiseMetricPNG } from './plot';
export class MAPairwiseScorePlotPanel extends CollapsableControls {
    constructor() {
        super(...arguments);
        this.interactivity = new BehaviorSubject({});
        this.queue = new SingleAsyncQueue();
    }
    defaultState() {
        return {
            header: 'Predicted Aligned Error',
            isCollapsed: false,
            isHidden: true,
            brand: { accent: 'purple', svg: ScatterPlotSvg },
            params: {},
            values: undefined,
            dataSources: [],
        };
    }
    toggleCollapsed() {
        if (!this.state.isCollapsed) {
            this.setState({ isCollapsed: true });
        }
        else {
            const state = getPropsAndValues(this.plugin, this.state.values);
            this.setState({
                ...state,
                isCollapsed: false,
                isHidden: state.params.data.options.length === 0 || state.params.model.options.length === 0
            });
        }
    }
    ;
    componentDidMount() {
        this.subscribe(combineLatest([
            this.plugin.state.data.events.changed,
            this.plugin.behaviors.state.isAnimating
        ]), ([_, anim]) => {
            if (anim || this.state.isCollapsed)
                return;
            const state = getPropsAndValues(this.plugin, this.state.values);
            this.setState({
                ...state,
                isHidden: state.params.data.options.length === 0 || state.params.model.options.length === 0
            });
        });
        this.subscribe(filterHighlightState(this.interactivity), state => {
            highlightState(this.plugin, state);
        });
        this.subscribe(filterOverpaintState(this.interactivity), state => {
            this.queue.enqueue(() => overpaintState(this.plugin, state));
        });
    }
    renderControls() {
        const { params, values, dataSources } = this.state;
        return _jsxs(_Fragment, { children: [_jsx(ParameterControls, { params: params, values: values, onChangeValues: values => this.setState({ values }) }), _jsx(PlotWrapper, { plugin: this.plugin, values: values, dataSources: dataSources, interactivity: this.interactivity })] });
    }
}
export function MAPairwiseScorePlot({ plugin, model, pairwiseMetric }) {
    var _a;
    const _interactivity = useRef();
    const interactivity = (_a = _interactivity.current) !== null && _a !== void 0 ? _a : (_interactivity.current = new BehaviorSubject({}));
    useEffect(() => {
        const queue = new SingleAsyncQueue();
        const highlight = filterHighlightState(interactivity).subscribe(state => highlightState(plugin, state));
        const paint = filterOverpaintState(interactivity).subscribe(state => queue.enqueue(() => overpaintState(plugin, state)));
        return () => {
            highlight.unsubscribe();
            paint.unsubscribe();
            queue.enqueue(() => overpaintState(plugin, interactivity.value));
        };
    }, [model, pairwiseMetric]);
    return _jsx(MAPairwiseScorePlotBase, { model: model, pairwiseMetric: pairwiseMetric, interactivity: interactivity });
}
function filterHighlightState(state) {
    return state.pipe(throttleTime(16, undefined, { leading: true, trailing: true }), distinctUntilChanged((a, b) => a.crosshairOffset === b.crosshairOffset));
}
function filterOverpaintState(state) {
    return state.pipe(throttleTime(66, undefined, { leading: true, trailing: true }), distinctUntilChanged((a, b) => a.boxStart === b.boxStart && (a.mouseDown ? a.crosshairOffset : a.boxEnd) === (b.mouseDown ? b.crosshairOffset : b.boxEnd)));
}
const PlotWrapper = memo(({ plugin, values, dataSources, interactivity }) => {
    var _a, _b, _c;
    const model = (_b = (_a = plugin.managers.structure.hierarchy.current.models.find(m => m.cell.transform.ref === values.model)) === null || _a === void 0 ? void 0 : _a.cell.obj) === null || _b === void 0 ? void 0 : _b.data;
    const src = dataSources.find(src => src.id === values.data);
    const cif = (_c = plugin.state.data.cells.get(src === null || src === void 0 ? void 0 : src.dataRef)) === null || _c === void 0 ? void 0 : _c.obj;
    const block = cif === null || cif === void 0 ? void 0 : cif.data.blocks[src === null || src === void 0 ? void 0 : src.blockIndex];
    if (!model || !block || !src)
        return _jsx("div", { className: 'msp-description', children: "Data not available" });
    const metric = QualityAssessment.pairwiseMetricFromModelArchiveCIF(model, block, src.metridId);
    if (!metric)
        return _jsx("div", { className: 'msp-description', children: "Data not available" });
    return _jsx(MAPairwiseScorePlotBase, { interactivity: interactivity, model: model, pairwiseMetric: metric });
}, (prev, next) => prev.values.data === next.values.data && prev.values.model === next.values.model);
function getPropsAndValues(plugin, current) {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j;
    const models = plugin.managers.structure.hierarchy.current.models;
    const cifs = plugin.state.data.selectQ(q => q.root.subtree().ofType(PluginStateObject.Format.Cif));
    const dataSources = [];
    for (const cif of cifs) {
        if (!((_a = cif.obj) === null || _a === void 0 ? void 0 : _a.data.blocks))
            continue;
        let blockIndex = 0;
        for (const block of cif.obj.data.blocks) {
            for (const pae of QualityAssessment.findModelArchiveCIFPAEMetrics(block)) {
                dataSources.push({
                    id: `${cif.transform.ref}:${blockIndex}:${pae.id}`,
                    metridId: pae.id,
                    label: `${block.header}: ${pae.name}`,
                    dataRef: cif.transform.ref,
                    blockIndex,
                });
            }
            blockIndex++;
        }
    }
    const params = {
        model: PD.Select((_b = models[0]) === null || _b === void 0 ? void 0 : _b.cell.transform.ref, models.map(m => { var _a; return [m.cell.transform.ref, (_a = m.cell.obj) === null || _a === void 0 ? void 0 : _a.data.label]; }), { isHidden: models.length <= 1 }),
        data: PD.Select((_c = dataSources[0]) === null || _c === void 0 ? void 0 : _c.id, dataSources.map(o => [o.id, o.label]), { isHidden: dataSources.length <= 1 })
    };
    const values = {
        model: (_e = (_d = params.model.options.find(o => o[0] === (current === null || current === void 0 ? void 0 : current.model))) === null || _d === void 0 ? void 0 : _d[0]) !== null && _e !== void 0 ? _e : (_f = params.model.options[0]) === null || _f === void 0 ? void 0 : _f[0],
        data: (_h = (_g = params.data.options.find(o => o[0] === (current === null || current === void 0 ? void 0 : current.data))) === null || _g === void 0 ? void 0 : _g[0]) !== null && _h !== void 0 ? _h : (_j = params.data.options[0]) === null || _j === void 0 ? void 0 : _j[0],
    };
    return { params, values, dataSources };
}
const PlotSize = 1000;
const PlotOffset = 120;
const PlotColors = {
    ScoredOverpaint: Color(0xFFA500),
    ScoredLabel: Color(0xBC7100),
    AlignedOverpaint: Color(0x1AFFBB),
    AlignedLabel: Color(0x0F8E68),
};
export const MAPairwiseScorePlotBase = memo(({ model, pairwiseMetric, interactivity }) => {
    const interactivityRect = useRef();
    const drawing = maDrawPairwiseMetricPNG(model, pairwiseMetric);
    useEffect(() => {
        if (!drawing) {
            interactivity.next({});
            return;
        }
        interactivity.next({ model, drawing });
        const moveEvent = (ev) => {
            const current = interactivity.value;
            if (!current.inside && !current.mouseDown)
                return;
            const offset = getPlotMouseOffsetBase(interactivityRect.current, ev.clientX, ev.clientY);
            interactivity.next({ ...current, crosshairOffset: offset });
        };
        const mouseUpEvent = (ev) => {
            if (!interactivity.value.mouseDown)
                return;
            const offset = getPlotMouseOffsetBase(interactivityRect.current, ev.clientX, ev.clientY);
            interactivity.next({ ...interactivity.value, mouseDown: false, boxEnd: offset });
        };
        window.addEventListener('mousemove', moveEvent);
        window.addEventListener('mouseup', mouseUpEvent);
        return () => {
            window.removeEventListener('mousemove', moveEvent);
            window.removeEventListener('mouseup', mouseUpEvent);
        };
    }, [model, interactivity, drawing]);
    if (!drawing)
        return _jsx(_Fragment, { children: "Not available" });
    const { metric, colorRange, chains, png } = drawing;
    const nResidues = metric.residueRange[1] - metric.residueRange[0];
    const border = '#333';
    const line = '#000';
    const legendHeight = 80;
    const legendOffsetY = PlotOffset + PlotSize + 50;
    const viewBox = '0 0 1140 1270';
    return _jsxs("div", { style: { margin: '8px 8px 0 8px', position: 'relative' }, children: [_jsxs("svg", { viewBox: viewBox, width: '100%', children: [_jsx("image", { x: PlotOffset + 1, y: PlotOffset + 1, width: PlotSize - 1, height: PlotSize - 1, href: png }), _jsx("line", { x1: PlotOffset, x2: PlotOffset + PlotSize, y1: PlotOffset, y2: PlotOffset + PlotSize, style: { stroke: line, strokeDasharray: '15,15' } }), _jsxs("linearGradient", { id: 'legend-gradient', x1: 0, x2: 1, y1: 0, y2: 0, children: [_jsx("stop", { offset: '0%', stopColor: colorRange[0] }), _jsx("stop", { offset: '100%', stopColor: colorRange[1] })] }), _jsx("rect", { x: PlotOffset, y: legendOffsetY, width: PlotSize, height: legendHeight, style: { fill: 'url(#legend-gradient)', strokeWidth: 1, stroke: border } }), _jsxs("text", { x: PlotOffset + 20, y: legendOffsetY + legendHeight - 22, style: { fontSize: '45px', fill: 'white', fontWeight: 'bold' }, children: [round(metric.valueRange[0], 2), " \u00C5"] }), _jsxs("text", { x: PlotOffset + PlotSize - 20, y: legendOffsetY + legendHeight - 22, style: { fontSize: '45px', fill: 'black', fontWeight: 'bold' }, textAnchor: 'end', children: [round(metric.valueRange[1], 2), " \u00C5"] }), _jsx("text", { x: PlotOffset + PlotSize / 2, y: legendOffsetY + legendHeight - 22, style: { fontSize: '45px', fill: 'black' }, textAnchor: 'middle', children: "Predicted Aligned Error" }), _jsx("text", { x: PlotOffset + PlotSize / 2, y: 50, style: { fontSize: '45px', fontWeight: 'bold', fill: Color.toStyle(PlotColors.ScoredLabel) }, textAnchor: 'middle', children: "Scored Residue" }), _jsx("text", { className: 'msp-svg-text', style: { fontSize: '50px', fontWeight: 'bold', fill: Color.toStyle(PlotColors.AlignedLabel) }, transform: `translate(50, ${PlotOffset + PlotSize / 2}) rotate(270)`, textAnchor: 'middle', children: "Aligned Residue" }), chains.map(({ startOffset, endOffset, label }) => {
                        const textOffset = PlotOffset + PlotSize * (startOffset + (endOffset - startOffset) / 2) / nResidues;
                        const endLineOffset = PlotOffset + PlotSize * endOffset / nResidues;
                        const startLineOffset = PlotOffset + PlotSize * startOffset / nResidues;
                        const seq_id = model.atomicHierarchy.residues.label_seq_id;
                        const startIndex = seq_id.value(metric.residueRange[0] + startOffset);
                        const endIndex = seq_id.value(metric.residueRange[0] + endOffset - 1);
                        return _jsxs(Fragment, { children: [_jsxs("text", { x: textOffset, y: PlotOffset - 15, className: 'msp-svg-text', style: { fontSize: '40px' }, textAnchor: 'middle', children: [label, " ", startIndex, "-", endIndex] }), _jsxs("text", { className: 'msp-svg-text', style: { fontSize: '40px' }, transform: `translate(${PlotOffset - 15}, ${textOffset}) rotate(270)`, textAnchor: 'middle', children: [label, " ", startIndex, "-", endIndex] }), _jsx("line", { x1: startLineOffset, x2: startLineOffset, y1: PlotOffset - 20, y2: PlotOffset + PlotSize + 20, style: { stroke: line, strokeDasharray: '15,15' } }), _jsx("line", { x1: endLineOffset, x2: endLineOffset, y1: PlotOffset - 20, y2: PlotOffset + PlotSize + 20, style: { stroke: line, strokeDasharray: '15,15' } }), _jsx("line", { x1: PlotOffset - 20, x2: PlotOffset + PlotSize + 20, y1: startLineOffset, y2: startLineOffset, style: { stroke: line, strokeDasharray: '15,15' } }), _jsx("line", { x1: PlotOffset - 20, x2: PlotOffset + PlotSize + 20, y1: endLineOffset, y2: endLineOffset, style: { stroke: line, strokeDasharray: '15,15' } })] }, startOffset);
                    })] }), _jsxs("svg", { viewBox: viewBox, style: { position: 'absolute', inset: 0 }, children: [_jsx("rect", { x: PlotOffset, y: PlotOffset, width: PlotSize, height: PlotSize, style: { fill: 'transparent', cursor: 'crosshair' }, ref: interactivityRect, onMouseMove: (ev) => {
                            interactivity.next({ ...interactivity.value, inside: true });
                            ev.currentTarget.style.stroke = 'black';
                            ev.currentTarget.style.strokeWidth = '4px';
                        }, onMouseDown: (ev) => {
                            interactivity.next({ ...interactivity.value, mouseDown: true, boxStart: getPlotMouseOffset(ev) });
                        }, onMouseLeave: (ev) => {
                            interactivity.next({ ...interactivity.value, inside: false, crosshairOffset: undefined });
                            ev.currentTarget.style.stroke = '#333';
                            ev.currentTarget.style.strokeWidth = '1px';
                        } }), _jsx(PlotInteractivity, { drawing: drawing, interactity: interactivity })] })] });
}, (prev, next) => prev.model === next.model && prev.pairwiseMetric === next.pairwiseMetric);
function PlotInteractivity({ drawing, interactity }) {
    const state = useBehavior(interactity);
    const { crosshairOffset, inside } = state;
    const box = getBox(state);
    const label = getCrosshairLabel(state);
    let labelNode;
    if (label) {
        const labelStyle = label ? { fontSize: '45px', fill: 'black', fontWeight: 'bold', pointerEvents: 'none', userSelect: 'none' } : undefined;
        let x, y, anchor;
        if (crosshairOffset[0] < PlotSize / 2) {
            x = PlotOffset + crosshairOffset[0] + 20;
            anchor = 'start';
        }
        else {
            x = PlotOffset + crosshairOffset[0] - 20;
            anchor = 'end';
        }
        if (crosshairOffset[1] < PlotSize / 2) {
            y = PlotOffset + crosshairOffset[1] + 65;
        }
        else {
            y = PlotOffset + crosshairOffset[1] - (label[2] ? 3 * 45 : 2 * 45) + 20;
        }
        labelNode = _jsxs("text", { y: y, style: labelStyle, textAnchor: anchor, children: [_jsxs("tspan", { x: x, children: ["S: ", label[0]] }), _jsxs("tspan", { x: x, dy: 45, children: ["A: ", label[1]] }), label[2] && _jsx("tspan", { x: x, dy: 45, children: label[2] })] });
    }
    return _jsxs(_Fragment, { children: [inside && crosshairOffset && _jsx("line", { x1: crosshairOffset[0] + PlotOffset, x2: crosshairOffset[0] + PlotOffset, y1: PlotOffset, y2: PlotOffset + PlotSize, style: { pointerEvents: 'none', stroke: 'black', strokeDasharray: '5,5' } }), inside && crosshairOffset && _jsx("line", { x1: PlotOffset, x2: PlotOffset + PlotSize, y1: crosshairOffset[1] + PlotOffset, y2: crosshairOffset[1] + PlotOffset, style: { pointerEvents: 'none', stroke: 'black', strokeDasharray: '5,5' } }), box && _jsx("rect", { x: PlotOffset + box[0], y: PlotOffset + box[1], width: box[2], height: box[3], style: { stroke: '#eee', strokeWidth: 4, fill: 'rgba(0, 0, 0, 0.15)', pointerEvents: 'none' } }), labelNode] });
}
function getCrosshairLabel(state) {
    var _a, _b, _c;
    if (!state.drawing || !state.crosshairOffset || !state.inside)
        return;
    const { drawing } = state;
    const rA = getResidueIndex(drawing, clamp(state.crosshairOffset[0], 0, PlotSize));
    const rB = getResidueIndex(drawing, clamp(state.crosshairOffset[1], 0, PlotSize));
    const value = (_b = (_a = drawing.metric.values[rA]) === null || _a === void 0 ? void 0 : _a[rB]) !== null && _b !== void 0 ? _b : (_c = drawing.metric.values[rB]) === null || _c === void 0 ? void 0 : _c[rA];
    const valueLabel = typeof value === 'number' ? `${round(value, 2)} Å` : '';
    return [getResidueLabel(drawing, rA), getResidueLabel(drawing, rB), valueLabel];
}
function getResidueIndex(drawing, offset) {
    const rI = drawing.metric.residueRange[0] + Math.round(offset / PlotSize * (drawing.metric.residueRange[1] - drawing.metric.residueRange[0] + 1));
    return clamp(rI, drawing.metric.residueRange[0], drawing.metric.residueRange[1]);
}
function getResidueLabel(drawing, rI) {
    const hierarchy = drawing.model.atomicHierarchy;
    const asym_id = hierarchy.chains.label_asym_id;
    const seq_id = hierarchy.residues.label_seq_id;
    const comp_id = hierarchy.atoms.label_comp_id;
    return `${asym_id.value(AtomicHierarchy.residueChainIndex(hierarchy, rI))} ${seq_id.value(rI)} ${comp_id.value(AtomicHierarchy.residueFirstAtomIndex(hierarchy, rI))}`;
}
function getBox(state) {
    const start = state.boxStart;
    const end = state.mouseDown ? state.crosshairOffset : state.boxEnd;
    if (!start || !end)
        return undefined;
    const x = clamp(Math.min(start[0], end[0]), 0, PlotSize);
    const width = clamp(Math.max(start[0], end[0]), 0, PlotSize) - x;
    const y = clamp(Math.min(start[1], end[1]), 0, PlotSize);
    const height = clamp(Math.max(start[1], end[1]), 0, PlotSize) - y;
    if (width < 1 && height < 1)
        return undefined;
    return [x, y, width, height];
}
function getPlotMouseOffset(ev) {
    return getPlotMouseOffsetBase(ev.currentTarget, ev.clientX, ev.clientY);
}
function getPlotMouseOffsetBase(target, clientX, clientY) {
    const rect = target.getBoundingClientRect();
    const offsetX = PlotSize * (clientX - rect.left) / rect.width;
    const offsetY = PlotSize * (clientY - rect.top) / rect.height;
    return [offsetX, offsetY];
}
function findModelRef(plugin, model) {
    var _a;
    if (!model)
        return undefined;
    for (const m of plugin.managers.structure.hierarchy.current.models) {
        if (((_a = m.cell.obj) === null || _a === void 0 ? void 0 : _a.data) === model)
            return m;
    }
    return undefined;
}
function highlightState(plugin, state) {
    var _a, _b, _c;
    const structure = (_c = (_b = (_a = findModelRef(plugin, state.model)) === null || _a === void 0 ? void 0 : _a.structures[0]) === null || _b === void 0 ? void 0 : _b.cell.obj) === null || _c === void 0 ? void 0 : _c.data;
    if (!state.drawing || !state.crosshairOffset || !state.inside || !structure) {
        plugin.managers.interactivity.lociHighlights.clearHighlights();
        return;
    }
    const { drawing } = state;
    const rA = getResidueIndex(drawing, clamp(state.crosshairOffset[0], 0, PlotSize));
    const rB = getResidueIndex(drawing, clamp(state.crosshairOffset[1], 0, PlotSize));
    const resIdx = StructureProperties.residue.key;
    const loci = StructureQuery.loci(atoms({
        residueTest: ctx => {
            const rI = resIdx(ctx.element);
            return rI === rA || rI === rB;
        },
    }), structure);
    plugin.managers.interactivity.lociHighlights.highlightOnly({ loci });
}
async function overpaintState(plugin, state) {
    var _a, _b;
    const tag = 'modelarchive-pae-overpaint';
    const overpaints = plugin.state.data.selectQ(q => q.root.subtree().withTag(tag));
    const update = plugin.build();
    for (const overpaint of overpaints)
        update.delete(overpaint);
    const model = findModelRef(plugin, state.model);
    const structure = (_b = (_a = model === null || model === void 0 ? void 0 : model.structures[0]) === null || _a === void 0 ? void 0 : _a.cell.obj) === null || _b === void 0 ? void 0 : _b.data;
    if (!state.drawing || !state.boxStart || !(state.boxEnd || state.crosshairOffset) || !structure) {
        if (!overpaints)
            return;
        return reApplyRepresentationStates(plugin, update);
    }
    const start = state.boxStart;
    const end = state.mouseDown ? state.crosshairOffset : state.boxEnd;
    const x0 = clamp(Math.min(start[0], end[0]), 0, PlotSize);
    const x1 = clamp(Math.max(start[0], end[0]), 0, PlotSize);
    const y0 = clamp(Math.min(start[1], end[1]), 0, PlotSize);
    const y1 = clamp(Math.max(start[1], end[1]), 0, PlotSize);
    if (x1 - x0 <= 1 || y1 - y0 <= 1) {
        if (!overpaints)
            return;
        return reApplyRepresentationStates(plugin, update);
    }
    const representations = plugin.state.data.selectQ(q => q.byRef(model.cell.transform.ref)
        .subtree()
        .ofType(PluginStateObject.Molecule.Structure.Representation3D));
    const resIdx = StructureProperties.residue.key;
    const startScored = getResidueIndex(state.drawing, x0);
    const endScored = getResidueIndex(state.drawing, x1);
    const lociScored = StructureQuery.loci(atoms({
        residueTest: ctx => {
            const rI = resIdx(ctx.element);
            return rI >= startScored && rI <= endScored;
        },
    }), structure);
    const startAligned = getResidueIndex(state.drawing, y0);
    const endAligned = getResidueIndex(state.drawing, y1);
    const lociAligned = StructureQuery.loci(atoms({
        residueTest: ctx => {
            const rI = resIdx(ctx.element);
            return rI >= startAligned && rI <= endAligned;
        },
    }), structure);
    const layers = [{
            bundle: StructureElement.Bundle.fromSubStructure(structure, structure),
            color: Color(0x777777),
            clear: false,
        }, {
            bundle: StructureElement.Bundle.fromLoci(lociScored),
            color: PlotColors.ScoredOverpaint,
            clear: false,
        }, {
            bundle: StructureElement.Bundle.fromLoci(lociAligned),
            color: PlotColors.AlignedOverpaint,
            clear: false,
        }];
    for (const repr of representations) {
        update.to(repr).apply(OverpaintStructureRepresentation3DFromBundle, { layers }, { tags: [tag], state: { isGhost: true } });
    }
    return update.commit();
}
async function reApplyRepresentationStates(plugin, update) {
    var _a, _b;
    await update.commit();
    const states = plugin.state.data.selectQ(q => q.root.subtree().ofType(PluginStateObject.Molecule.Structure.Representation3DState));
    for (const state of states) {
        const data = (_a = state.obj) === null || _a === void 0 ? void 0 : _a.data;
        if (!data)
            continue;
        data.repr.setState(data.state);
        (_b = plugin.canvas3d) === null || _b === void 0 ? void 0 : _b.update(data.repr);
    }
}
