/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export const IsHiddenCustomStateExtension = {
    id: 'ww-pdb/is-hidden-custom-state',
    description: 'Allow updating initial visibility of nodes',
    createExtensionContext: () => ({}),
    action: (updateTarget, node) => {
        var _a;
        if (!node.custom || !((_a = node.custom) === null || _a === void 0 ? void 0 : _a.is_hidden))
            return;
        updateTarget.update.to(updateTarget.selector).updateState({ isHidden: true });
    },
};
