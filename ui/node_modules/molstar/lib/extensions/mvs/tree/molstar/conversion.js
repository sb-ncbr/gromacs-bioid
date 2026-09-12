/**
 * Copyright (c) 2023-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { omitObjectKeys, pickObjectKeys } from '../../../../mol-util/object';
import { addDefaults, condenseTree, convertTree, dfs, resolveUris } from '../generic/tree-utils';
import { MVSTreeSchema } from '../mvs/mvs-tree';
/** Convert `format` parameter of `parse` node in `MolstarTree`
 * into `format` and `is_binary` parameters in `MolstarTree` */
export const ParseFormatMvsToMolstar = {
    mmcif: { format: 'cif', is_binary: false },
    bcif: { format: 'cif', is_binary: true },
    pdb: { format: 'pdb', is_binary: false },
    map: { format: 'map', is_binary: true },
};
/** Conversion rules for conversion from `MVSTree` (with all parameter values) to `MolstarTree` */
const mvsToMolstarConversionRules = {
    'download': node => [],
    'parse': (node, parent) => {
        const { format, is_binary } = ParseFormatMvsToMolstar[node.params.format];
        const convertedNode = { kind: 'parse', params: { ...node.params, format }, custom: node.custom, ref: node.ref };
        if ((parent === null || parent === void 0 ? void 0 : parent.kind) === 'download') {
            return [
                { kind: 'download', params: { ...parent.params, is_binary }, custom: parent.custom, ref: parent.ref },
                convertedNode,
            ];
        }
        else {
            console.warn('"parse" node is not being converted, this is suspicious');
            return [convertedNode];
        }
    },
    'structure': (node, parent) => {
        if ((parent === null || parent === void 0 ? void 0 : parent.kind) !== 'parse')
            throw new Error(`Parent of "structure" must be "parse", not "${parent === null || parent === void 0 ? void 0 : parent.kind}".`);
        const { format } = ParseFormatMvsToMolstar[parent.params.format];
        return [
            { kind: 'trajectory', params: { format, ...pickObjectKeys(node.params, ['block_header', 'block_index']) } },
            { kind: 'model', params: pickObjectKeys(node.params, ['model_index']) },
            { kind: 'structure', params: omitObjectKeys(node.params, ['block_header', 'block_index', 'model_index']), custom: node.custom, ref: node.ref },
        ];
    },
};
/** Node kinds in `MolstarTree` that it makes sense to condense */
const molstarNodesToCondense = new Set(['download', 'parse', 'trajectory', 'model']);
/** Convert MolViewSpec tree into MolStar tree */
export function convertMvsToMolstar(mvsTree, sourceUrl) {
    const full = addDefaults(mvsTree, MVSTreeSchema);
    if (sourceUrl)
        resolveUris(full, sourceUrl, ['uri', 'url']);
    const converted = convertTree(full, mvsToMolstarConversionRules);
    if (converted.kind !== 'root')
        throw new Error("Root's type is not 'root' after conversion from MVS tree to Molstar tree.");
    const condensed = condenseTree(converted, molstarNodesToCondense);
    return condensed;
}
function fileExtensionMatches(filename, extensions) {
    filename = filename.toLowerCase();
    return extensions.some(ext => ext === '*' || filename.endsWith(ext));
}
const StructureFormatExtensions = {
    mmcif: ['.cif', '.mmif'],
    bcif: ['.bcif'],
    pdb: ['.pdb', '.ent'],
    map: ['.map', '.ccp4', '.mrc', '.mrcs'],
};
/** Run some sanity check on a MVSTree. Return a list of potential problems (`undefined` if there are none) */
export function mvsSanityCheckIssues(tree) {
    const result = [];
    dfs(tree, (node, parent) => {
        if (node.kind === 'parse' && (parent === null || parent === void 0 ? void 0 : parent.kind) === 'download') {
            const source = parent.params.url;
            const extensions = StructureFormatExtensions[node.params.format];
            if (!fileExtensionMatches(source, extensions)) {
                result.push(`Parsing data from ${source} as ${node.params.format} format might be a mistake. The file extension doesn't match recommended file extensions (${extensions.join(', ')})`);
            }
        }
    });
    return result.length > 0 ? result : undefined;
}
/** Run some sanity check on a MVSTree and print potential issues to the console. */
export function mvsSanityCheck(tree) {
    const issues = mvsSanityCheckIssues(tree);
    if (issues) {
        console.warn('There are potential issues in the MVS tree:');
        for (const issue of issues) {
            console.warn(' ', issue);
        }
    }
}
