/**
 * Copyright (c) 2021-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { PluginBehavior } from '../../../mol-plugin/behavior/behavior';
import { DefaultQueryRuntimeTable } from '../../../mol-script/runtime/query/compiler';
import { PLDDTConfidenceColorThemeProvider } from './color/plddt';
import { QualityAssessment, QualityAssessmentProvider } from './prop';
import { StructureSelectionCategory, StructureSelectionQuery } from '../../../mol-plugin-state/helpers/structure-selection-query';
import { MolScriptBuilder as MS } from '../../../mol-script/language/builder';
import { OrderedSet } from '../../../mol-data/int';
import { cantorPairing } from '../../../mol-data/util';
import { QmeanScoreColorThemeProvider } from './color/qmean';
import { PresetStructureRepresentations, StructureRepresentationPresetProvider } from '../../../mol-plugin-state/builder/structure/representation-preset';
import { StateObjectRef } from '../../../mol-state';
import { MAPairwiseScorePlotPanel } from './pairwise/ui';
import { PluginConfigItem } from '../../../mol-plugin/config';
export const MAQualityAssessmentConfig = {
    EnablePairwiseScorePlot: new PluginConfigItem('ma-quality-assessment-prop.enable-pairwise-score-plot', true),
};
export const MAQualityAssessment = PluginBehavior.create({
    name: 'ma-quality-assessment-prop',
    category: 'custom-props',
    display: {
        name: 'Quality Assessment',
        description: 'Data included in Model Archive files.'
    },
    ctor: class extends PluginBehavior.Handler {
        constructor() {
            super(...arguments);
            this.provider = QualityAssessmentProvider;
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
            DefaultQueryRuntimeTable.addCustomProp(this.provider.descriptor);
            this.ctx.customModelProperties.register(this.provider, this.params.autoAttach);
            this.ctx.managers.lociLabels.addProvider(this.labelProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.add(PLDDTConfidenceColorThemeProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.add(QmeanScoreColorThemeProvider);
            this.ctx.query.structure.registry.add(confidentPLDDT);
            this.ctx.builders.structure.representation.registerPreset(QualityAssessmentPLDDTPreset);
            this.ctx.builders.structure.representation.registerPreset(QualityAssessmentQmeanPreset);
            if (this.ctx.config.get(MAQualityAssessmentConfig.EnablePairwiseScorePlot)) {
                this.ctx.customStructureControls.set('ma-quality-assessment-pairwise-plot', MAPairwiseScorePlotPanel);
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
            DefaultQueryRuntimeTable.removeCustomProp(this.provider.descriptor);
            this.ctx.customStructureProperties.unregister(this.provider.descriptor.name);
            this.ctx.managers.lociLabels.removeProvider(this.labelProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.remove(PLDDTConfidenceColorThemeProvider);
            this.ctx.representation.structure.themes.colorThemeRegistry.remove(QmeanScoreColorThemeProvider);
            this.ctx.query.structure.registry.remove(confidentPLDDT);
            this.ctx.builders.structure.representation.unregisterPreset(QualityAssessmentPLDDTPreset);
            this.ctx.builders.structure.representation.unregisterPreset(QualityAssessmentQmeanPreset);
            this.ctx.customStructureControls.delete('ma-quality-assessment-pairwise-plot');
        }
    },
    params: () => ({
        autoAttach: PD.Boolean(false),
        showTooltip: PD.Boolean(true),
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
        const metrics = (_a = QualityAssessmentProvider.get(unit.model).value) === null || _a === void 0 ? void 0 : _a.local;
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
            OrderedSet.forEach(indices, idx => {
                const eI = elements[idx];
                const rI = residueIndex[eI];
                const residueKey = cantorPairing(rI, unit.id);
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
const confidentPLDDT = StructureSelectionQuery('Confident pLDDT (> 70)', MS.struct.modifier.union([
    MS.struct.modifier.wholeResidues([
        MS.struct.modifier.union([
            MS.struct.generator.atomGroups({
                'chain-test': MS.core.rel.eq([MS.ammp('objectPrimitive'), 'atomistic']),
                'residue-test': MS.core.rel.gr([QualityAssessment.symbols.pLDDT.symbol(), 70]),
            })
        ])
    ])
]), {
    description: 'Select residues with a pLDDT > 70 (confident).',
    category: StructureSelectionCategory.Validation,
    ensureCustomProperties: async (ctx, structure) => {
        for (const m of structure.models) {
            await QualityAssessmentProvider.attach(ctx, m, void 0, true);
        }
    }
});
//
export const QualityAssessmentPLDDTPreset = StructureRepresentationPresetProvider({
    id: 'preset-structure-representation-ma-quality-assessment-plddt',
    display: {
        name: 'Quality Assessment (pLDDT)', group: 'Annotation',
        description: 'Color structure based on pLDDT Confidence.'
    },
    isApplicable(a) {
        return !!a.data.models.some(m => QualityAssessment.isApplicable(m, 'pLDDT'));
    },
    params: () => StructureRepresentationPresetProvider.CommonParams,
    async apply(ref, params, plugin) {
        var _a;
        const structureCell = StateObjectRef.resolveAndCheck(plugin.state.data, ref);
        const structure = (_a = structureCell === null || structureCell === void 0 ? void 0 : structureCell.obj) === null || _a === void 0 ? void 0 : _a.data;
        if (!structureCell || !structure)
            return {};
        const colorTheme = PLDDTConfidenceColorThemeProvider.name;
        return await PresetStructureRepresentations.auto.apply(ref, { ...params, theme: { globalName: colorTheme, focus: { name: colorTheme } } }, plugin);
    }
});
export const QualityAssessmentQmeanPreset = StructureRepresentationPresetProvider({
    id: 'preset-structure-representation-ma-quality-assessment-qmean',
    display: {
        name: 'Quality Assessment (QMEAN)', group: 'Annotation',
        description: 'Color structure based on QMEAN Score.'
    },
    isApplicable(a) {
        return !!a.data.models.some(m => QualityAssessment.isApplicable(m, 'qmean'));
    },
    params: () => StructureRepresentationPresetProvider.CommonParams,
    async apply(ref, params, plugin) {
        var _a;
        const structureCell = StateObjectRef.resolveAndCheck(plugin.state.data, ref);
        const structure = (_a = structureCell === null || structureCell === void 0 ? void 0 : structureCell.obj) === null || _a === void 0 ? void 0 : _a.data;
        if (!structureCell || !structure)
            return {};
        const colorTheme = QmeanScoreColorThemeProvider.name;
        return await PresetStructureRepresentations.auto.apply(ref, { ...params, theme: { globalName: colorTheme, focus: { name: colorTheme } } }, plugin);
    }
});
