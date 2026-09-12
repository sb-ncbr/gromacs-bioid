"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ExternalStructureColorThemeProvider = exports.ExternalStructureColorThemeParams = void 0;
exports.ExternalStructureColorTheme = ExternalStructureColorTheme;
const color_1 = require("../../mol-util/color");
const param_definition_1 = require("../../mol-util/param-definition");
const location_iterator_1 = require("../../mol-geo/util/location-iterator");
const categories_1 = require("./categories");
const selection_1 = require("../../mol-state/state/selection");
const objects_1 = require("../../mol-plugin-state/objects");
const structure_1 = require("../../mol-model/structure");
const chain_id_1 = require("./chain-id");
const entity_id_1 = require("./entity-id");
const entity_source_1 = require("./entity-source");
const molecule_type_1 = require("./molecule-type");
const model_index_1 = require("./model-index");
const structure_index_1 = require("./structure-index");
const type_helpers_1 = require("../../mol-util/type-helpers");
const lookup3d_1 = require("../../mol-model/structure/structure/util/lookup3d");
const structure_selection_query_1 = require("../../mol-plugin-state/helpers/structure-selection-query");
const vec3_1 = require("../../mol-math/linear-algebra/3d/vec3");
const Description = `Assigns a color based on structure property at a given vertex.`;
exports.ExternalStructureColorThemeParams = {
    structure: param_definition_1.ParamDefinition.ValueRef((ctx) => {
        const structures = ctx.state.data.select(selection_1.StateSelection.Generators.rootsOfType(objects_1.PluginStateObject.Molecule.Structure)).filter(c => { var _a; return (_a = c.obj) === null || _a === void 0 ? void 0 : _a.data; });
        return structures.map(v => { var _a, _b; return [v.transform.ref, (_b = (_a = v.obj) === null || _a === void 0 ? void 0 : _a.label) !== null && _b !== void 0 ? _b : '<unknown>']; });
    }, (ref, getData) => getData(ref)),
    style: param_definition_1.ParamDefinition.MappedStatic('chain-id', {
        'chain-id': param_definition_1.ParamDefinition.Group(chain_id_1.ChainIdColorThemeParams),
        'entity-id': param_definition_1.ParamDefinition.Group(entity_id_1.EntityIdColorThemeParams),
        'entity-source': param_definition_1.ParamDefinition.Group(entity_source_1.EntitySourceColorThemeParams),
        'molecule-type': param_definition_1.ParamDefinition.Group(molecule_type_1.MoleculeTypeColorThemeParams),
        'model-index': param_definition_1.ParamDefinition.Group(model_index_1.ModelIndexColorThemeParams),
        'structure-index': param_definition_1.ParamDefinition.Group(structure_index_1.StructureIndexColorThemeParams),
    }),
    defaultColor: param_definition_1.ParamDefinition.Color((0, color_1.Color)(0xcccccc)),
    maxDistance: param_definition_1.ParamDefinition.Numeric(8, { min: 0.1, max: 24, step: 0.1 }, { description: 'Maximum distance to search for the nearest structure element. This is done only if the approximate search fails.' }),
    approxMaxDistance: param_definition_1.ParamDefinition.Numeric(4, { min: 0, max: 12, step: 0.1 }, { description: 'Maximum distance to search for an approximately nearest structure element. This is done before the extact search.' }),
    normalOffset: param_definition_1.ParamDefinition.Numeric(0, { min: -10, max: 20, step: 0.1 }, { description: 'Offset vertex position along its normal by given amount.' }),
    backboneOnly: param_definition_1.ParamDefinition.Boolean(false),
};
function getStyleTheme(ctx, props) {
    switch (props.name) {
        case 'chain-id': return (0, chain_id_1.ChainIdColorTheme)(ctx, props.params);
        case 'entity-id': return (0, entity_id_1.EntityIdColorTheme)(ctx, props.params);
        case 'entity-source': return (0, entity_source_1.EntitySourceColorTheme)(ctx, props.params);
        case 'molecule-type': return (0, molecule_type_1.MoleculeTypeColorTheme)(ctx, props.params);
        case 'model-index': return (0, model_index_1.ModelIndexColorTheme)(ctx, props.params);
        case 'structure-index': return (0, structure_index_1.StructureIndexColorTheme)(ctx, props.params);
        default: (0, type_helpers_1.assertUnreachable)(props);
    }
}
function ExternalStructureColorTheme(ctx, props) {
    let structure;
    try {
        structure = props.structure.getValue();
    }
    catch (_a) {
        // .getValue() is resolved during state reconciliation => would throw from UI
    }
    // NOTE: this will currently be slow for with GPU/texture meshes due to slow iteration
    // TODO: create texture to be able to do the sampling on the GPU
    let color;
    let contextHash = undefined;
    let legend = undefined;
    const { maxDistance, approxMaxDistance: approxDistance, normalOffset, defaultColor, backboneOnly } = props;
    if (structure) {
        const styleTheme = getStyleTheme({ ...ctx, structure }, props.style);
        const lookupFirstCtx = (0, lookup3d_1.StructureLookup3DResultContext)();
        const lookupNearestCtx = (0, lookup3d_1.StructureLookup3DResultContext)();
        let s = structure;
        if (backboneOnly) {
            s = structure_1.StructureSelection.unionStructure(structure_selection_query_1.StructureSelectionQueries.backbone.query(new structure_1.QueryContext(structure)));
        }
        const position = (0, vec3_1.Vec3)();
        const l = structure_1.StructureElement.Location.create(s);
        color = (location, isSecondary) => {
            if (!(0, location_iterator_1.isPositionLocation)(location)) {
                return defaultColor;
            }
            // Offset the vertex position along its normal
            if (normalOffset !== 0) {
                vec3_1.Vec3.scaleAndAdd(position, location.position, location.normal, normalOffset);
            }
            else {
                vec3_1.Vec3.copy(position, location.position);
            }
            const [x, y, z] = position;
            if (approxDistance > 0) {
                const rf = s.lookup3d.approxNearest(x, y, z, approxDistance, lookupFirstCtx);
                if (rf.count > 0) {
                    l.unit = rf.units[0];
                    l.element = l.unit.elements[rf.indices[0]];
                    return styleTheme.color(l, isSecondary);
                }
            }
            const rn = s.lookup3d.find(x, y, z, maxDistance, lookupNearestCtx);
            if (rn.count > 0) {
                let idx = 0;
                let minD = rn.squaredDistances[0];
                for (let i = 1; i < rn.count; ++i) {
                    if (rn.squaredDistances[i] < minD) {
                        minD = rn.squaredDistances[i];
                        idx = i;
                    }
                }
                l.unit = rn.units[idx];
                l.element = l.unit.elements[rn.indices[idx]];
                return styleTheme.color(l, isSecondary);
            }
            return defaultColor;
        };
        contextHash = styleTheme.contextHash;
        legend = styleTheme.legend;
    }
    else {
        color = () => defaultColor;
    }
    return {
        factory: ExternalStructureColorTheme,
        granularity: 'vertex',
        preferSmoothing: true,
        color,
        props,
        contextHash,
        description: Description,
        legend,
    };
}
exports.ExternalStructureColorThemeProvider = {
    name: 'external-structure',
    label: 'External Structure',
    category: categories_1.ColorThemeCategory.Misc,
    factory: ExternalStructureColorTheme,
    getParams: () => exports.ExternalStructureColorThemeParams,
    defaultValues: param_definition_1.ParamDefinition.getDefaultValues(exports.ExternalStructureColorThemeParams),
    isApplicable: (ctx) => true,
};
