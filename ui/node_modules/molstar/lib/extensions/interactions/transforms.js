/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { Mesh } from '../../mol-geo/geometry/mesh/mesh';
import { InteractionsParams } from '../../mol-model-props/computed/interactions';
import { PluginStateObject as SO } from '../../mol-plugin-state/objects';
import { StateTransformer } from '../../mol-state';
import { Task } from '../../mol-task';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { computeContacts } from './compute';
import { getCustomInteractionData } from './custom';
import { buildInteractionsShape, InteractionVisualParams } from './visuals';
const Factory = StateTransformer.builderFactory('interactions-extension');
export class InteractionData extends SO.Create({ name: 'Interactions', typeClass: 'Data' }) {
}
export const ComputeContacts = Factory({
    name: 'compute-contacts',
    display: 'Compute Contacts',
    from: SO.Molecule.Structure.Selections,
    to: InteractionData,
    params: {
        interactions: PD.Group(InteractionsParams),
    },
})({
    apply({ params, a }) {
        return Task.create('Compute Contacts', async (ctx) => {
            const interactions = await computeContacts(ctx, a.data, { interactions: params.interactions });
            return new InteractionData({ interactions }, { label: 'Interactions' });
        });
    }
});
export const CustomInteractions = Factory({
    name: 'custom-interactions',
    display: 'Custom Interactions',
    from: SO.Root,
    to: InteractionData,
    params: {
        interactions: PD.Value([], { isHidden: true }),
    },
})({
    apply({ params, dependencies }) {
        return Task.create('Custom Interactions', async (ctx) => {
            const structures = {};
            for (const [k, v] of Object.entries(dependencies !== null && dependencies !== void 0 ? dependencies : {})) {
                structures[k] = v.data;
            }
            const interactions = getCustomInteractionData(params.interactions, structures);
            return new InteractionData({ interactions }, { label: 'Custom Interactions' });
        });
    }
});
export const InteractionsShape = Factory({
    name: 'interactions-shape',
    display: { name: 'Interactions Shape' },
    from: InteractionData,
    to: SO.Shape.Provider,
    params: InteractionVisualParams
})({
    canAutoUpdate: () => true,
    apply({ a, params }) {
        return new SO.Shape.Provider({
            label: 'Interactions Shape Provider',
            data: { interactions: a.data.interactions, params },
            params: PD.withDefaults(Mesh.Params, {}),
            getShape: (_, data, __, prev) => buildInteractionsShape(data.interactions, data.params, prev === null || prev === void 0 ? void 0 : prev.geometry),
            geometryUtils: Mesh.Utils,
        }, { label: 'Interactions Shape Provider' });
    }
});
