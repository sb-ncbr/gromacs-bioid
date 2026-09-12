"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.FormalChargeColorThemeProvider = exports.FormalChargeColorThemeParams = void 0;
exports.getFormalChargeColorThemeParams = getFormalChargeColorThemeParams;
exports.FormalChargeColorTheme = FormalChargeColorTheme;
const color_1 = require("../../mol-util/color");
const structure_1 = require("../../mol-model/structure");
const param_definition_1 = require("../../mol-util/param-definition");
const categories_1 = require("./categories");
const lists_1 = require("../../mol-util/color/lists");
const DefaultFormalChargeColor = (0, color_1.Color)(0xffff99);
const Description = `Assigns a color based on the formal charge of an atom.`;
exports.FormalChargeColorThemeParams = {
    domain: param_definition_1.ParamDefinition.Interval([-3, 3]),
    list: param_definition_1.ParamDefinition.ColorList({ kind: 'set', colors: lists_1.ColorLists['red-white-blue'].list }),
};
function getFormalChargeColorThemeParams(ctx) {
    return exports.FormalChargeColorThemeParams; // TODO return copy
}
function getFormalCharge(unit, element) {
    if (structure_1.Unit.isAtomic(unit)) {
        return unit.model.atomicHierarchy.atoms.pdbx_formal_charge.value(element);
    }
    else {
        return 0;
    }
}
function FormalChargeColorTheme(ctx, props) {
    const scale = color_1.ColorScale.create({
        domain: props.domain,
        listOrName: props.list.colors,
    });
    function color(location) {
        if (structure_1.StructureElement.Location.is(location)) {
            const fc = getFormalCharge(location.unit, location.element);
            return fc !== undefined ? scale.color(fc) : DefaultFormalChargeColor;
        }
        else if (structure_1.Bond.isLocation(location)) {
            const fc = getFormalCharge(location.aUnit, location.aUnit.elements[location.aIndex]);
            return fc !== undefined ? scale.color(fc) : DefaultFormalChargeColor;
        }
        return DefaultFormalChargeColor;
    }
    return {
        factory: FormalChargeColorTheme,
        granularity: 'group',
        preferSmoothing: true,
        color,
        props,
        description: Description,
        legend: scale ? scale.legend : undefined
    };
}
exports.FormalChargeColorThemeProvider = {
    name: 'formal-charge',
    label: 'Formal Charge',
    category: categories_1.ColorThemeCategory.Atom,
    factory: FormalChargeColorTheme,
    getParams: getFormalChargeColorThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.FormalChargeColorThemeParams),
    isApplicable: (ctx) => !!ctx.structure && ctx.structure.models.some(m => m.atomicHierarchy.atoms.pdbx_formal_charge.isDefined)
};
