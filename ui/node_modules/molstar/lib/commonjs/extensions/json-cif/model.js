"use strict";
/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.JSONCifVERSION = void 0;
exports.getJSONCifCategory = getJSONCifCategory;
exports.JSONCifVERSION = '0.1.0';
function getJSONCifCategory(block, name) {
    return block.categories[name];
}
