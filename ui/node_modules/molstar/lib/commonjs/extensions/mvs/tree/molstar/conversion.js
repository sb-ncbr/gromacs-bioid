"use strict";
/**
 * Copyright (c) 2023-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Adam Midlik <midlik@gmail.com>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ParseFormatMvsToMolstar = void 0;
exports.convertMvsToMolstar = convertMvsToMolstar;
exports.mvsSanityCheckIssues = mvsSanityCheckIssues;
exports.mvsSanityCheck = mvsSanityCheck;
const object_1 = require("../../../../mol-util/object");
const tree_utils_1 = require("../generic/tree-utils");
const mvs_tree_1 = require("../mvs/mvs-tree");
/** Convert `format` parameter of `parse` node in `MolstarTree`
 * into `format` and `is_binary` parameters in `MolstarTree` */
exports.ParseFormatMvsToMolstar = {
    mmcif: { format: 'cif', is_binary: false },
    bcif: { format: 'cif', is_binary: true },
    pdb: { format: 'pdb', is_binary: false },
    map: { format: 'map', is_binary: true },
};
/** Conversion rules for conversion from `MVSTree` (with all parameter values) to `MolstarTree` */
const mvsToMolstarConversionRules = {
    'download': node => [],
    'parse': (node, parent) => {
        const { format, is_binary } = exports.ParseFormatMvsToMolstar[node.params.format];
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
        const { format } = exports.ParseFormatMvsToMolstar[parent.params.format];
        return [
            { kind: 'trajectory', params: { format, ...(0, object_1.pickObjectKeys)(node.params, ['block_header', 'block_index']) } },
            { kind: 'model', params: (0, object_1.pickObjectKeys)(node.params, ['model_index']) },
            { kind: 'structure', params: (0, object_1.omitObjectKeys)(node.params, ['block_header', 'block_index', 'model_index']), custom: node.custom, ref: node.ref },
        ];
    },
};
/** Node kinds in `MolstarTree` that it makes sense to condense */
const molstarNodesToCondense = new Set(['download', 'parse', 'trajectory', 'model']);
/** Convert MolViewSpec tree into MolStar tree */
function convertMvsToMolstar(mvsTree, sourceUrl) {
    const full = (0, tree_utils_1.addDefaults)(mvsTree, mvs_tree_1.MVSTreeSchema);
    if (sourceUrl)
        (0, tree_utils_1.resolveUris)(full, sourceUrl, ['uri', 'url']);
    const converted = (0, tree_utils_1.convertTree)(full, mvsToMolstarConversionRules);
    if (converted.kind !== 'root')
        throw new Error("Root's type is not 'root' after conversion from MVS tree to Molstar tree.");
    const condensed = (0, tree_utils_1.condenseTree)(converted, molstarNodesToCondense);
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
function mvsSanityCheckIssues(tree) {
    const result = [];
    (0, tree_utils_1.dfs)(tree, (node, parent) => {
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
function mvsSanityCheck(tree) {
    const issues = mvsSanityCheckIssues(tree);
    if (issues) {
        console.warn('There are potential issues in the MVS tree:');
        for (const issue of issues) {
            console.warn(' ', issue);
        }
    }
}
