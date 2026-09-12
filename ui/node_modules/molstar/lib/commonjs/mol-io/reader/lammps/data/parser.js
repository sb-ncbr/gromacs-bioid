"use strict";
/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseLammpsData = parseLammpsData;
const mol_task_1 = require("../../../../mol-task");
const tokenizer_1 = require("../../common/text/tokenizer");
const result_1 = require("../../result");
const token_1 = require("../../common/text/column/token");
const db_1 = require("../../../../mol-data/db");
const { readLine, skipWhitespace, eatValue, eatLine, markStart } = tokenizer_1.Tokenizer;
const reWhitespace = /\s+/;
function State(tokenizer, runtimeCtx) {
    return {
        tokenizer,
        runtimeCtx,
    };
}
async function handleAtoms(state, count, atom_style) {
    const { tokenizer } = state;
    // default atom style is atomic
    // depending on the atom style the number of columns can change
    const atomId = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const moleculeId = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const atomType = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const charge = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const x = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const y = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const z = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const columns = {
        full: [atomId, moleculeId, atomType, charge, x, y, z],
        atomic: [atomId, atomType, x, y, z],
        bond: [atomId, moleculeId, atomType, x, y, z],
    };
    const n = columns[atom_style].length;
    const { position } = tokenizer;
    readLine(tokenizer).trim();
    tokenizer.position = position;
    const { length } = tokenizer;
    let linesAlreadyRead = 0;
    await (0, mol_task_1.chunkedSubtask)(state.runtimeCtx, 100000, void 0, chunkSize => {
        const linesToRead = Math.min(count - linesAlreadyRead, chunkSize);
        for (let i = 0; i < linesToRead; ++i) {
            for (let j = 0; j < n; ++j) {
                skipWhitespace(tokenizer);
                markStart(tokenizer);
                eatValue(tokenizer);
                const column = columns[atom_style][j];
                if (column) {
                    tokenizer_1.TokenBuilder.addUnchecked(column, tokenizer.tokenStart, tokenizer.tokenEnd);
                }
            }
            // ignore any extra columns
            eatLine(tokenizer);
            markStart(tokenizer);
        }
        linesAlreadyRead += linesToRead;
        return linesToRead;
    }, ctx => ctx.update({ message: 'Parsing...', current: tokenizer.position, max: length }));
    return {
        count,
        atomId: (0, token_1.TokenColumnProvider)(atomId)(db_1.Column.Schema.int),
        moleculeId: (0, token_1.TokenColumnProvider)(moleculeId)(db_1.Column.Schema.int),
        atomType: (0, token_1.TokenColumnProvider)(atomType)(db_1.Column.Schema.int),
        charge: (0, token_1.TokenColumnProvider)(charge)(db_1.Column.Schema.float),
        x: (0, token_1.TokenColumnProvider)(x)(db_1.Column.Schema.float),
        y: (0, token_1.TokenColumnProvider)(y)(db_1.Column.Schema.float),
        z: (0, token_1.TokenColumnProvider)(z)(db_1.Column.Schema.float),
    };
}
async function handleBonds(state, count) {
    const { tokenizer } = state;
    const bondId = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const bondType = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const atomIdA = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const atomIdB = tokenizer_1.TokenBuilder.create(tokenizer.data, count * 2);
    const { length } = tokenizer;
    let bondsAlreadyRead = 0;
    await (0, mol_task_1.chunkedSubtask)(state.runtimeCtx, 10, void 0, chunkSize => {
        const bondsToRead = Math.min(count - bondsAlreadyRead, chunkSize);
        for (let i = 0; i < bondsToRead; ++i) {
            for (let j = 0; j < 4; ++j) {
                skipWhitespace(tokenizer);
                markStart(tokenizer);
                eatValue(tokenizer);
                switch (j) {
                    case 0:
                        tokenizer_1.TokenBuilder.addUnchecked(bondId, tokenizer.tokenStart, tokenizer.tokenEnd);
                        break;
                    case 1:
                        tokenizer_1.TokenBuilder.addUnchecked(bondType, tokenizer.tokenStart, tokenizer.tokenEnd);
                        break;
                    case 2:
                        tokenizer_1.TokenBuilder.addUnchecked(atomIdA, tokenizer.tokenStart, tokenizer.tokenEnd);
                        break;
                    case 3:
                        tokenizer_1.TokenBuilder.addUnchecked(atomIdB, tokenizer.tokenStart, tokenizer.tokenEnd);
                        break;
                }
            }
        }
        bondsAlreadyRead += bondsToRead;
        return bondsToRead;
    }, ctx => ctx.update({ message: 'Parsing...', current: tokenizer.position, max: length }));
    return {
        count,
        bondId: (0, token_1.TokenColumnProvider)(bondId)(db_1.Column.Schema.int),
        bondType: (0, token_1.TokenColumnProvider)(bondType)(db_1.Column.Schema.int),
        atomIdA: (0, token_1.TokenColumnProvider)(atomIdA)(db_1.Column.Schema.int),
        atomIdB: (0, token_1.TokenColumnProvider)(atomIdB)(db_1.Column.Schema.int),
    };
}
const AtomStyles = ['full', 'atomic', 'bond'];
async function parseInternal(data, ctx) {
    const tokenizer = (0, tokenizer_1.Tokenizer)(data);
    const state = State(tokenizer, ctx);
    let atoms = undefined;
    let bonds = undefined;
    let numAtoms = 0;
    let numBonds = 0;
    let atom_style = 'full';
    // full list of atom_style
    // https://docs.lammps.org/atom_style.html
    while (tokenizer.tokenEnd < tokenizer.length) {
        const line = readLine(state.tokenizer).trim();
        if (line.includes('atoms')) {
            numAtoms = parseInt(line.split(reWhitespace)[0]);
        }
        else if (line.includes('bonds')) {
            numBonds = parseInt(line.split(reWhitespace)[0]);
        }
        else if (line.includes('Masses')) {
            // TODO: support masses
        }
        else if (line.includes('Atoms')) {
            // usually atom style is indicated as a comment after Atoms. e.g. Atoms # full
            const parts = line.split('#');
            if (parts.length > 1) {
                const atomStyle = parts[1].trim();
                if (AtomStyles.includes(atomStyle)) {
                    atom_style = atomStyle;
                }
                else {
                    console.warn(`Unknown atom style: ${atomStyle}`);
                }
            }
            atoms = await handleAtoms(state, numAtoms, atom_style);
        }
        else if (line.includes('Bonds')) {
            bonds = await handleBonds(state, numBonds);
        }
    }
    if (atoms === undefined) {
        return result_1.ReaderResult.error('no atoms data');
    }
    if (bonds === undefined) {
        bonds = {
            count: 0,
            bondId: db_1.Column.ofIntArray([]),
            bondType: db_1.Column.ofIntArray([]),
            atomIdA: db_1.Column.ofIntArray([]),
            atomIdB: db_1.Column.ofIntArray([]),
        };
    }
    const result = {
        atoms,
        bonds
    };
    return result_1.ReaderResult.success(result);
}
function parseLammpsData(data) {
    return mol_task_1.Task.create('Parse LammpsData', async (ctx) => {
        return await parseInternal(data, ctx);
    });
}
