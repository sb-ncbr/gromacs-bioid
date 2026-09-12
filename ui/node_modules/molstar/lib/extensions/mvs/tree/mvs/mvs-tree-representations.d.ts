/**
 * Copyright (c) 2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { OptionalField } from '../generic/field-schema';
import { SimpleParamsSchema, UnionParamsSchema } from '../generic/params-schema';
export declare const MVSRepresentationParams: UnionParamsSchema<"type", {
    cartoon: SimpleParamsSchema<{
        /** Scales the corresponding visuals */
        size_factor: OptionalField<number>;
        /** Simplify corkscrew helices to tubes. */
        tubular_helices: OptionalField<boolean>;
    }>;
    ball_and_stick: SimpleParamsSchema<{
        /** Scales the corresponding visuals */
        size_factor: OptionalField<number>;
        /** Controls whether hydrogen atoms are drawn. */
        ignore_hydrogens: OptionalField<boolean>;
    }>;
    spacefill: SimpleParamsSchema<{
        /** Scales the corresponding visuals */
        size_factor: OptionalField<number>;
        /** Controls whether hydrogen atoms are drawn. */
        ignore_hydrogens: OptionalField<boolean>;
    }>;
    carbohydrate: SimpleParamsSchema<{
        /** Scales the corresponding visuals */
        size_factor: OptionalField<number>;
    }>;
    surface: SimpleParamsSchema<{
        /** Scales the corresponding visuals */
        size_factor: OptionalField<number>;
        /** Controls whether hydrogen atoms are drawn. */
        ignore_hydrogens: OptionalField<boolean>;
    }>;
}>;
export declare const MVSVolumeRepresentationParams: UnionParamsSchema<"type", {
    isosurface: SimpleParamsSchema<{
        /** Relative isovalue. */
        relative_isovalue: OptionalField<number | null>;
        /** Absolute isovalue. Overrides `relative_isovalue`. */
        absolute_isovalue: OptionalField<number | null>;
        /** Show mesh wireframe. Defaults to false. */
        show_wireframe: OptionalField<boolean>;
        /** Show mesh faces. Defaults to true. */
        show_faces: OptionalField<boolean>;
    }>;
}>;
