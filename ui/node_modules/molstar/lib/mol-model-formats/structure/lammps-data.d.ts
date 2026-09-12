/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 */
import { LammpsDataFile, UnitStyle } from '../../mol-io/reader/lammps/schema';
import { Trajectory } from '../../mol-model/structure';
import { Task } from '../../mol-task';
import { ModelFormat } from '../format';
export { LammpsDataFormat };
type LammpsDataFormat = ModelFormat<LammpsDataFile>;
declare namespace LammpsDataFormat {
    function is(x?: ModelFormat): x is LammpsDataFormat;
    function create(mol: LammpsDataFile): LammpsDataFormat;
}
export declare function trajectoryFromLammpsData(mol: LammpsDataFile, unitsStyle?: UnitStyle): Task<Trajectory>;
