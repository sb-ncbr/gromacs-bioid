/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
export const JSONCifVERSION = '0.1.0';
export function getJSONCifCategory(block, name) {
    return block.categories[name];
}
