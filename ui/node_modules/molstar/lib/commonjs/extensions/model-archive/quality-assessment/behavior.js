"use strict";
/**
 * Copyright (c) 2021-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.QualityAssessmentQmeanPreset = exports.QualityAssessmentPLDDTPreset = exports.MAQualityAssessment = exports.MAQualityAssessmentConfig = void 0;
const param_definition_1 = require("../../../mol-util/param-definition");
const behavior_1 = require("../../../mol-plugin/behavior/behavior");
const compiler_1 = require("../../../mol-script/runtime/query/compiler");
const plddt_1 = require("./color/plddt");
const prop_1 = require("./prop");
const structure_selection_query_1 = require("../../../mol-plugin-state/helpers/structure-selection-query");
const builder_1 = require("../../../mol-script/language/builder");
const int_1 = require("../../../mol-data/int");
const util_1 = require("../../../mol-data/util");
const qmean_1 = require("./color/qmean");
const representation_preset_1 = require("../../../mol-plugin-state/builder/structure/representation-preset");
const mol_state_1 = require("../../../mol-state");
const ui_1 = require("./pairwise/ui");
const config_1 = require("../../../mol-plugin/config");
exports.MAQualityAssessmentConfig = {
    EnablePairwiseScorePlot: new config_1.PluginConfigItem('ma-quality-assessment-prop.enable-pairwise-score-plot', true),
};
exports.MAQualityAssessment = behavior_1.PluginBehavior.create({
    name: 'ma-quality-assessment-prop',
    category: 'custom-props',
    display: {
        name: 'Quality Assessment',
        description: 'Data included in Model Archive files.'
    },
    ctor: class extends behavior_1.PluginBehavior.Handler {
        constructor() {
            super(...arguments);
            this.provider = prop_1.QualityAssessmentProvider;
            this.labelProvider = {
                label: (loci) => {
                    var _a;
                    if (!this.params.showTooltip)
                        return;
                    return (_a = metricLabels(loci)) === null || _a === void 0 ? void 0 : _a.join('</br>');
                }
            };
        }
        register() {
            compiler_1.DefaultQueryRuntimeTable.addCustomProp(this.provider.descriptor);
            this.ctx.customModelProperties.register(this.provider, this.params.autoAttach);
            this.ctx.managers.lociLabels.addProvider(this.labelProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.add(plddt_1.PLDDTConfidenceColorThemeProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.add(qmean_1.QmeanScoreColorThemeProvider);
            this.ctx.query.structure.registry.add(confidentPLDDT);
            this.ctx.builders.structure.representation.registerPreset(exports.QualityAssessmentPLDDTPreset);
            this.ctx.builders.structure.representation.registerPreset(exports.QualityAssessmentQmeanPreset);
            if (this.ctx.config.get(exports.MAQualityAssessmentConfig.EnablePairwiseScorePlot)) {
                this.ctx.customStructureControls.set('ma-quality-assessment-pairwise-plot', ui_1.MAPairwiseScorePlotPanel);
            }
        }
        update(p) {
            const updated = this.params.autoAttach !== p.autoAttach;
            this.params.autoAttach = p.autoAttach;
            this.params.showTooltip = p.showTooltip;
            this.ctx.customStructureProperties.setDefaultAutoAttach(this.provider.descriptor.name, this.params.autoAttach);
            return updated;
        }
        unregister() {
            compiler_1.DefaultQueryRuntimeTable.removeCustomProp(this.provider.descriptor);
            this.ctx.customStructureProperties.unregister(this.provider.descriptor.name);
            this.ctx.managers.lociLabels.removeProvider(this.labelProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.remove(plddt_1.PLDDTConfidenceColorThemeProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.remove(qmean_1.QmeanScoreColorThemeProvider);
            this.ctx.query.structure.registry.remove(confidentPLDDT);
            this.ctx.builders.structure.representation.unregisterPreset(exports.QualityAssessmentPLDDTPreset);
            this.ctx.builders.structure.representation.unregisterPreset(exports.QualityAssessmentQmeanPreset);
            this.ctx.customStructureControls.delete('ma-quality-assessment-pairwise-plot');
        }
    },
    params: () => ({
        autoAttach: param_definition_1.ParamDefinition.Boolean(false),
        showTooltip: param_definition_1.ParamDefinition.Boolean(true),
    })
});
//
function plddtCategory(score) {
    if (score > 50 && score <= 70)
        return 'Low';
    if (score > 70 && score <= 90)
        return 'Confident';
    if (score > 90)
        return 'Very high';
    return 'Very low';
}
function buildLabel(metric, scoreAvg, countInfo) {
    let label = metric.name;
    if (metric.type !== metric.name)
        label += ` (${metric.type})`;
    if (countInfo)
        label += countInfo;
    label += `: ${scoreAvg.toFixed(2)}`;
    if (metric.kind === 'pLDDT')
        label += ` <small>(${plddtCategory(scoreAvg)})</small>`;
    return label;
}
function metricLabels(loci) {
    var _a;
    if (loci.kind !== 'element-loci')
        return;
    if (loci.elements.length === 0)
        return;
    const seenMetrics = [];
    const aggregates = new Map();
    for (const { indices, unit } of loci.elements) {
        const metrics = (_a = prop_1.QualityAssessmentProvider.get(unit.model).value) === null || _a === void 0 ? void 0 : _a.local;
        if (!metrics)
            continue;
        const residueIndex = unit.model.atomicHierarchy.residueAtomSegments.index;
        const { elements } = unit;
        for (const metric of metrics) {
            const key = `${metric.name}-${metric.type}`;
            let aggregate = aggregates.get(key);
            if (!aggregate) {
                aggregate = { metric, scoreSum: 0, seenResidues: new Set() };
                aggregates.set(key, aggregate);
                seenMetrics.push(aggregate);
            }
            const values = metric.values;
            const { seenResidues } = aggregate;
            int_1.OrderedSet.forEach(indices, idx => {
                const eI = elements[idx];
                const rI = residueIndex[eI];
                const residueKey = (0, util_1.cantorPairing)(rI, unit.id);
                if (seenResidues.has(residueKey))
                    return;
                const score = values.get(residueIndex[eI]);
                if (typeof score === 'undefined')
                    return;
                aggregate.scoreSum += score;
                aggregate.seenResidues.add(residueKey);
            });
        }
    }
    if (seenMetrics.length === 0)
        return;
    const labels = [];
    for (const { metric, scoreSum, seenResidues } of seenMetrics) {
        let countInfo = '';
        if (seenResidues.size > 1) {
            countInfo = ` <small>(${seenResidues.size} Residues avg.)</small>`;
        }
        const scoreAvg = scoreSum / seenResidues.size;
        const label = buildLabel(metric, scoreAvg, countInfo);
        labels.push(label);
    }
    return labels;
}
//
const confidentPLDDT = (0, structure_selection_query_1.StructureSelectionQuery)('Confident pLDDT (> 70)', builder_1.MolScriptBuilder.struct.modifier.union([
    builder_1.MolScriptBuilder.struct.modifier.wholeResidues([
        builder_1.MolScriptBuilder.struct.modifier.union([
            builder_1.MolScriptBuilder.struct.generator.atomGroups({
                'chain-test': builder_1.MolScriptBuilder.core.rel.eq([builder_1.MolScriptBuilder.ammp('objectPrimitive'), 'atomistic']),
                'residue-test': builder_1.MolScriptBuilder.core.rel.gr([prop_1.QualityAssessment.symbols.pLDDT.symbol(), 70]),
            })
        ])
    ])
]), {
    description: 'Select residues with a pLDDT > 70 (confident).',
    category: structure_selection_query_1.StructureSelectionCategory.Validation,
    ensureCustomProperties: async (ctx, structure) => {
        for (const m of structure.models) {
            await prop_1.QualityAssessmentProvider.attach(ctx, m, void 0, true);
        }
    }
});
//
exports.QualityAssessmentPLDDTPreset = (0, representation_preset_1.StructureRepresentationPresetProvider)({
    id: 'preset-structure-representation-ma-quality-assessment-plddt',
    display: {
        name: 'Quality Assessment (pLDDT)', group: 'Annotation',
        description: 'Color structure based on pLDDT Confidence.'
    },
    isApplicable(a) {
        return !!a.data.models.some(m => prop_1.QualityAssessment.isApplicable(m, 'pLDDT'));
    },
    params: () => representation_preset_1.StructureRepresentationPresetProvider.CommonParams,
    async apply(ref, params, plugin) {
        var _a;
        const structureCell = mol_state_1.StateObjectRef.resolveAndCheck(plugin.state.data, ref);
        const structure = (_a = structureCell === null || structureCell === void 0 ? void 0 : structureCell.obj) === null || _a === void 0 ? void 0 : _a.data;
        if (!structureCell || !structure)
            return {};
        const colorTheme = plddt_1.PLDDTConfidenceColorThemeProvider.name;
        return await representation_preset_1.PresetStructureRepresentations.auto.apply(ref, { ...params, theme: { globalName: colorTheme, focus: { name: colorTheme } } }, plugin);
    }
});
exports.QualityAssessmentQmeanPreset = (0, representation_preset_1.StructureRepresentationPresetProvider)({
    id: 'preset-structure-representation-ma-quality-assessment-qmean',
    display: {
        name: 'Quality Assessment (QMEAN)', group: 'Annotation',
        description: 'Color structure based on QMEAN Score.'
    },
    isApplicable(a) {
        return !!a.data.models.some(m => prop_1.QualityAssessment.isApplicable(m, 'qmean'));
    },
    params: () => representation_preset_1.StructureRepresentationPresetProvider.CommonParams,
    async apply(ref, params, plugin) {
        var _a;
        const structureCell = mol_state_1.StateObjectRef.resolveAndCheck(plugin.state.data, ref);
        const structure = (_a = structureCell === null || structureCell === void 0 ? void 0 : structureCell.obj) === null || _a === void 0 ? void 0 : _a.data;
        if (!structureCell || !structure)
            return {};
        const colorTheme = qmean_1.QmeanScoreColorThemeProvider.name;
        return await representation_preset_1.PresetStructureRepresentations.auto.apply(ref, { ...params, theme: { globalName: colorTheme, focus: { name: colorTheme } } }, plugin);
    }
});
