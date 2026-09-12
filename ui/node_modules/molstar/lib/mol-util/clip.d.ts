/**
 * Copyright (c) 2021-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Mat4, Vec3 } from '../mol-math/linear-algebra';
import { ParamDefinition as PD } from './param-definition';
export interface Clip {
    variant: Clip.Variant;
    objects: Clip.Objects;
}
export declare function Clip(): void;
export declare namespace Clip {
    /** Clip object types */
    const Type: {
        none: number;
        plane: number;
        sphere: number;
        cube: number;
        cylinder: number;
        infiniteCone: number;
    };
    type Variant = 'instance' | 'pixel';
    type Objects = {
        count: number;
        type: number[];
        invert: boolean[];
        position: number[];
        rotation: number[];
        scale: number[];
        /** Transform point by this before testing */
        transform: number[];
    };
    const Params: {
        variant: PD.Select<Variant>;
        objects: PD.ObjectList<PD.Normalize<{
            type: "none" | "sphere" | "cube" | "plane" | "cylinder" | "infiniteCone";
            invert: boolean;
            position: Vec3;
            rotation: PD.Normalize<{
                axis: /*elided*/ any;
                angle: /*elided*/ any;
            }>;
            scale: Vec3;
            transform: Mat4;
        }>>;
    };
    type Params = typeof Params;
    type Props = PD.Values<Params>;
    function getClip(props: Props, clip?: Clip): Clip;
    function areEqual(cA: Clip, cB: Clip): boolean;
}
