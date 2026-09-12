/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { StructureElement } from '../../mol-model/structure';
export function getCustomInteractionData(interactions, structures) {
    const elements = [];
    for (const schema of interactions) {
        let info;
        if (schema.kind === 'covalent') {
            info = { kind: schema.kind, degree: schema.degree };
        }
        else {
            info = { kind: schema.kind };
        }
        elements.push({
            sourceSchema: schema,
            info,
            aStructureRef: schema.aStructureRef,
            a: resolveLoci(structures[schema.aStructureRef], schema.a),
            bStructureRef: schema.bStructureRef,
            b: resolveLoci(structures[schema.bStructureRef], schema.b),
        });
    }
    return { kind: 'structure-interactions', elements };
}
function resolveLoci(structure, schema) {
    return StructureElement.Schema.toLoci(structure, schema);
}
