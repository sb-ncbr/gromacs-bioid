"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.StructureSurroundings = exports.StructureSurroundingsParams = void 0;
const structure_1 = require("../../../mol-model/structure");
const structure_component_1 = require("../../../mol-plugin-state/helpers/structure-component");
const objects_1 = require("../../../mol-plugin-state/objects");
const builder_1 = require("../../../mol-script/language/builder");
const param_definition_1 = require("../../../mol-util/param-definition");
exports.StructureSurroundingsParams = {
    radius: param_definition_1.ParamDefinition.Numeric(5, { min: 0 }, { description: 'Surroundings radius in Angstroms' }),
    includeSelf: param_definition_1.ParamDefinition.Boolean(true, { description: 'Include parent selection itself in the surroundings' }),
    wholeResidues: param_definition_1.ParamDefinition.Boolean(true, { description: 'Include whole residues, instead of individual atoms' }),
    nullIfEmpty: param_definition_1.ParamDefinition.Optional(param_definition_1.ParamDefinition.Boolean(true, { isHidden: true })),
};
exports.StructureSurroundings = objects_1.PluginStateTransform.BuiltIn({
    name: 'structure-surroundings',
    display: { name: 'Surroundings', description: 'Surroundings of a structure component.' },
    from: objects_1.PluginStateObject.Molecule.Structure,
    to: objects_1.PluginStateObject.Molecule.Structure,
    params: exports.StructureSurroundingsParams,
})({
    apply({ a, params, cache }) {
        var _a;
        const struct = a.data;
        const rootStruct = (_a = struct.parent) !== null && _a !== void 0 ? _a : struct;
        const targetBundle = structure_1.StructureElement.Bundle.fromSubStructure(rootStruct, struct);
        const targetExpr = structure_1.StructureElement.Bundle.toExpression(targetBundle);
        let surroundingsExpr = builder_1.MolScriptBuilder.struct.modifier.includeSurroundings({
            0: targetExpr,
            radius: params.radius,
            'as-whole-residues': params.wholeResidues,
        });
        if (!params.includeSelf) {
            surroundingsExpr = builder_1.MolScriptBuilder.struct.modifier.exceptBy({
                0: surroundingsExpr,
                by: targetExpr,
            });
        }
        return (0, structure_component_1.createStructureComponent)(rootStruct, { label: `Surroundings (${params.radius} Å)`, type: { name: 'expression', params: surroundingsExpr }, nullIfEmpty: params.nullIfEmpty }, cache);
    },
    dispose({ b }) {
        b === null || b === void 0 ? void 0 : b.data.customPropertyDescriptors.dispose();
    }
});
