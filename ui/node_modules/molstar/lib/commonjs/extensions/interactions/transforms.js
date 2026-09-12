"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.InteractionsShape = exports.CustomInteractions = exports.ComputeContacts = exports.InteractionData = void 0;
const mesh_1 = require("../../mol-geo/geometry/mesh/mesh");
const interactions_1 = require("../../mol-model-props/computed/interactions");
const objects_1 = require("../../mol-plugin-state/objects");
const mol_state_1 = require("../../mol-state");
const mol_task_1 = require("../../mol-task");
const param_definition_1 = require("../../mol-util/param-definition");
const compute_1 = require("./compute");
const custom_1 = require("./custom");
const visuals_1 = require("./visuals");
const Factory = mol_state_1.StateTransformer.builderFactory('interactions-extension');
class InteractionData extends objects_1.PluginStateObject.Create({ name: 'Interactions', typeClass: 'Data' }) {
}
exports.InteractionData = InteractionData;
exports.ComputeContacts = Factory({
    name: 'compute-contacts',
    display: 'Compute Contacts',
    from: objects_1.PluginStateObject.Molecule.Structure.Selections,
    to: InteractionData,
    params: {
        interactions: param_definition_1.ParamDefinition.Group(interactions_1.InteractionsParams),
    },
})({
    apply({ params, a }) {
        return mol_task_1.Task.create('Compute Contacts', async (ctx) => {
            const interactions = await (0, compute_1.computeContacts)(ctx, a.data, { interactions: params.interactions });
            return new InteractionData({ interactions }, { label: 'Interactions' });
        });
    }
});
exports.CustomInteractions = Factory({
    name: 'custom-interactions',
    display: 'Custom Interactions',
    from: objects_1.PluginStateObject.Root,
    to: InteractionData,
    params: {
        interactions: param_definition_1.ParamDefinition.Value([], { isHidden: true }),
    },
})({
    apply({ params, dependencies }) {
        return mol_task_1.Task.create('Custom Interactions', async (ctx) => {
            const structures = {};
            for (const [k, v] of Object.entries(dependencies !== null && dependencies !== void 0 ? dependencies : {})) {
                structures[k] = v.data;
            }
            const interactions = (0, custom_1.getCustomInteractionData)(params.interactions, structures);
            return new InteractionData({ interactions }, { label: 'Custom Interactions' });
        });
    }
});
exports.InteractionsShape = Factory({
    name: 'interactions-shape',
    display: { name: 'Interactions Shape' },
    from: InteractionData,
    to: objects_1.PluginStateObject.Shape.Provider,
    params: visuals_1.InteractionVisualParams
})({
    canAutoUpdate: () => true,
    apply({ a, params }) {
        return new objects_1.PluginStateObject.Shape.Provider({
            label: 'Interactions Shape Provider',
            data: { interactions: a.data.interactions, params },
            params: param_definition_1.ParamDefinition.withDefaults(mesh_1.Mesh.Params, {}),
            getShape: (_, data, __, prev) => (0, visuals_1.buildInteractionsShape)(data.interactions, data.params, prev === null || prev === void 0 ? void 0 : prev.geometry),
            geometryUtils: mesh_1.Mesh.Utils,
        }, { label: 'Interactions Shape Provider' });
    }
});
