/**
 * Copyright (c) 2020-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 *
 * ported from https://github.com/photopea/UZIP.js/blob/master/UZIP.js
 * MIT License, Copyright (c) 2018 Photopea
 */
type CompressionStreamFormat = 'deflate' | 'deflate-raw' | 'gzip';
export declare function checkCompressionStreamSupport(format: CompressionStreamFormat): boolean;
export declare const U: {
    next_code: Uint16Array<ArrayBuffer>;
    bl_count: Uint16Array<ArrayBuffer>;
    ordr: number[];
    of0: number[];
    exb: number[];
    ldef: Uint16Array<ArrayBuffer>;
    df0: number[];
    dxb: number[];
    ddef: Uint32Array<ArrayBuffer>;
    flmap: Uint16Array<ArrayBuffer>;
    fltree: number[];
    fdmap: Uint16Array<ArrayBuffer>;
    fdtree: number[];
    lmap: Uint16Array<ArrayBuffer>;
    ltree: number[];
    ttree: number[];
    dmap: Uint16Array<ArrayBuffer>;
    dtree: number[];
    imap: Uint16Array<ArrayBuffer>;
    itree: number[];
    rev15: Uint16Array<ArrayBuffer>;
    lhst: Uint32Array<ArrayBuffer>;
    dhst: Uint32Array<ArrayBuffer>;
    ihst: Uint32Array<ArrayBuffer>;
    lits: Uint32Array<ArrayBuffer>;
    strt: Uint16Array<ArrayBuffer>;
    prev: Uint16Array<ArrayBuffer>;
};
export declare function codes2map(tree: number[], MAX_BITS: number, map: Uint16Array): void;
export declare function makeCodes(tree: number[], MAX_BITS: number): void;
export declare function revCodes(tree: number[], MAX_BITS: number): void;
export {};
