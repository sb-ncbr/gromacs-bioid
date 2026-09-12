"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.NonCovalentInteractionsExtension = void 0;
const transforms_1 = require("../../../mol-plugin-state/transforms");
const surroundings_1 = require("../components/surroundings");
const load_generic_1 = require("../load-generic");
const tree_schema_1 = require("../tree/generic/tree-schema");
const DefaultNonCovalentInteractionRadius = 5;
exports.NonCovalentInteractionsExtension = {
    id: 'wwpdb/non-covalent-interactions',
    description: 'Allow showing non-covalent interactions around components with molstar_show_non_covalent_interactions additional property',
    createExtensionContext: () => ({}),
    action: (updateTarget, node, context, extContext) => {
        var _a;
        if (node.kind !== 'component' && node.kind !== 'component_from_uri' && node.kind !== 'component_from_source')
            return;
        const customProps = (0, tree_schema_1.getCustomProps)(node);
        if (!customProps.molstar_show_non_covalent_interactions)
            return undefined;
        const surroundings = load_generic_1.UpdateTarget.apply(updateTarget, surroundings_1.StructureSurroundings, {
            radius: (_a = customProps.molstar_non_covalent_interactions_radius_ang) !== null && _a !== void 0 ? _a : DefaultNonCovalentInteractionRadius,
            includeSelf: true,
            wholeResidues: true,
            nullIfEmpty: false,
        });
        // Bubble on target
        load_generic_1.UpdateTarget.apply(updateTarget, transforms_1.StateTransforms.Representation.StructureRepresentation3D, {
            type: { name: 'ball-and-stick', params: { sizeFactor: 0.22, sizeAspectRatio: 0.73, adjustCylinderLength: true, xrayShaded: true, aromaticBonds: false, multipleBonds: 'off', excludeTypes: ['hydrogen-bond', 'metal-coordination'] } },
            colorTheme: { name: 'element-symbol', params: {} },
            sizeTheme: { name: 'physical', params: {} },
        });
        // Ball-and-stick on surrounding
        load_generic_1.UpdateTarget.apply(surroundings, transforms_1.StateTransforms.Representation.StructureRepresentation3D, {
            type: { name: 'ball-and-stick', params: { sizeFactor: 0.16, excludeTypes: ['hydrogen-bond', 'metal-coordination'] } },
            colorTheme: { name: 'element-symbol', params: {} },
            sizeTheme: { name: 'physical', params: {} },
        });
        // Non-covalent interactions
        load_generic_1.UpdateTarget.apply(surroundings, transforms_1.StateTransforms.Representation.StructureRepresentation3D, {
            type: { name: 'interactions', params: {} },
            colorTheme: { name: 'interaction-type', params: {} },
            sizeTheme: { name: 'uniform', params: {} },
        });
    },
};
