/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { Expression } from '../../../../mol-script/language/expression';
import { QueryContext } from '../../query';
import { Structure } from '../structure';
import { Bundle } from './bundle';
import { Loci } from './loci';
export interface SchemaItem {
    operator_name?: string;
    label_entity_id?: string;
    label_asym_id?: string;
    auth_asym_id?: string;
    label_seq_id?: number;
    auth_seq_id?: number;
    label_comp_id?: string;
    auth_comp_id?: string;
    pdbx_PDB_ins_code?: string;
    beg_label_seq_id?: number;
    end_label_seq_id?: number;
    beg_auth_seq_id?: number;
    end_auth_seq_id?: number;
    label_atom_id?: string;
    auth_atom_id?: string;
    type_symbol?: string;
    atom_id?: number;
    atom_index?: number;
}
export interface SchemaItems {
    prefix?: SchemaItem;
    items: SchemaItem[] | {
        [K in keyof SchemaItem]: SchemaItem[K][];
    };
}
export type Schema = SchemaItem | SchemaItems;
declare function toExpression(schema: Schema): Expression;
/**
 * Iterate over all items in a structure element schema.
 * @param schema Schema to iterate over
 * @param f Function called for each item in the schema.
 *          The value passed to the function can be mutable and should not be
 *          modified => make a copy if the value is used outside the callback.
 */
declare function forEachItem(schema: Schema, f: (item: SchemaItem) => void): void;
declare function toLoci(structure: Structure, schema: Schema, queryContext?: QueryContext): Loci;
declare function toBundle(structure: Structure, schema: Schema, queryContext?: QueryContext): Bundle;
export declare const Schema: {
    forEachItem: typeof forEachItem;
    toExpression: typeof toExpression;
    toLoci: typeof toLoci;
    toBundle: typeof toBundle;
};
export {};
