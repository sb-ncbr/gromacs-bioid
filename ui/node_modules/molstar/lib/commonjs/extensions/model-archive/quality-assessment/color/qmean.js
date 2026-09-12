"use strict";
/**
 * Copyright (c) 2021-25 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.QmeanScoreColorThemeProvider = void 0;
exports.getQmeanScoreColorThemeParams = getQmeanScoreColorThemeParams;
exports.QmeanScoreColorTheme = QmeanScoreColorTheme;
const prop_1 = require("../prop");
const structure_1 = require("../../../../mol-model/structure");
const color_1 = require("../../../../mol-util/color");
const param_definition_1 = require("../../../../mol-util/param-definition");
const categories_1 = require("../../../../mol-theme/color/categories");
const DefaultColor = (0, color_1.Color)(0xaaaaaa);
function getQmeanScoreColorThemeParams(ctx) {
    var _a;
    return {
        metricId: prop_1.QualityAssessment.getLocalOptions((_a = ctx.structure) === null || _a === void 0 ? void 0 : _a.models[0], 'qmean'),
    };
}
function QmeanScoreColorTheme(ctx, props) {
    let color = () => DefaultColor;
    const scale = color_1.ColorScale.create({
        domain: [0, 1],
        listOrName: [
            [(0, color_1.Color)(0xFF5000), 0.5], [(0, color_1.Color)(0x025AFD), 1.0]
        ]
    });
    if (ctx.structure) {
        const l = structure_1.StructureElement.Location.create(ctx.structure.root);
        const getColor = (location) => {
            var _a, _b, _c;
            const { unit, element } = location;
            if (!structure_1.Unit.isAtomic(unit))
                return DefaultColor;
            const qualityAssessment = prop_1.QualityAssessmentProvider.get(unit.model).value;
            const metric = (_b = (_a = qualityAssessment === null || qualityAssessment === void 0 ? void 0 : qualityAssessment.localMap.get(props.metricId)) === null || _a === void 0 ? void 0 : _a.values) !== null && _b !== void 0 ? _b : qualityAssessment === null || qualityAssessment === void 0 ? void 0 : qualityAssessment.qmean;
            const score = (_c = metric === null || metric === void 0 ? void 0 : metric.get(unit.model.atomicHierarchy.residueAtomSegments.index[element])) !== null && _c !== void 0 ? _c : -1;
            if (score < 0) {
                return DefaultColor;
            }
            else {
                return scale.color(score);
            }
        };
        color = (location) => {
            if (structure_1.StructureElement.Location.is(location)) {
                return getColor(location);
            }
            else if (structure_1.Bond.isLocation(location)) {
                l.unit = location.aUnit;
                l.element = location.aUnit.elements[location.aIndex];
                return getColor(l);
            }
            return DefaultColor;
        };
    }
    return {
        factory: QmeanScoreColorTheme,
        granularity: 'group',
        preferSmoothing: true,
        color,
        props,
        description: 'Assigns residue colors according to the QMEAN score.',
        legend: scale.legend
    };
}
exports.QmeanScoreColorThemeProvider = {
    name: 'qmean-score',
    label: 'QMEAN Score',
    category: categories_1.ColorThemeCategory.Validation,
    factory: QmeanScoreColorTheme,
    getParams: getQmeanScoreColorThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(getQmeanScoreColorThemeParams({})),
    isApplicable: (ctx) => { var _a; return !!((_a = ctx.structure) === null || _a === void 0 ? void 0 : _a.models.some(m => prop_1.QualityAssessment.isApplicable(m, 'qmean'))); },
    ensureCustomProperties: {
        attach: async (ctx, data) => {
            if (data.structure) {
                for (const m of data.structure.models) {
                    await prop_1.QualityAssessmentProvider.attach(ctx, m, void 0, true);
                }
            }
        },
        detach: async (data) => {
            if (data.structure) {
                for (const m of data.structure.models) {
                    prop_1.QualityAssessmentProvider.ref(m, false);
                }
            }
        }
    }
};
