/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Ludovic Autin <ludovic.autin@gmail.com>
 */
import { Column } from '../../../mol-data/db';
interface LammpsUnitStyle {
    mass: string;
    distance: string;
    time: string;
    energy: string;
    velocity: string;
    force: string;
    torque: string;
    temperature: string;
    pressure: string;
    viscosity: string;
    charge: string;
    dipole?: string;
    electricField?: string;
    density: string;
    scale: number;
}
export declare const lammpsUnitStyles: {
    [key: string]: LammpsUnitStyle;
};
export declare const UnitStyles: readonly ["real", "metal", "si", "cgs", "electron", "micro", "nano", "lj"];
export type UnitStyle = typeof UnitStyles[number];
export interface LammpsDataFile {
    readonly atoms: {
        readonly count: number;
        readonly atomId: Column<number>;
        readonly moleculeId: Column<number>;
        readonly atomType: Column<number>;
        readonly charge: Column<number>;
        readonly x: Column<number>;
        readonly y: Column<number>;
        readonly z: Column<number>;
    };
    readonly bonds: {
        readonly count: number;
        readonly bondId: Column<number>;
        readonly bondType: Column<number>;
        readonly atomIdA: Column<number>;
        readonly atomIdB: Column<number>;
    };
}
export interface LammpsBox {
    lower: [number, number, number];
    length: [number, number, number];
    periodicity: [string, string, string];
}
export interface LammpsFrame {
    count: number;
    atomMode: string;
    atomId: Column<number>;
    moleculeId: Column<number>;
    atomType: Column<number>;
    x: Column<number>;
    y: Column<number>;
    z: Column<number>;
}
export interface LammpsTrajectoryFile {
    frames: LammpsFrame[];
    times: number[];
    bounds: LammpsBox[];
    timeOffset: number;
    deltaTime: number;
}
export {};
