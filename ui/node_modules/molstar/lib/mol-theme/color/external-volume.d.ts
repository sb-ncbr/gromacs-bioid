/**
 * Copyright (c) 2024-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Cai Huiyu <szmun.caihy@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { ColorTheme } from '../color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../theme';
import { Volume } from '../../mol-model/volume';
export declare const ExternalVolumeColorThemeParams: {
    volume: PD.ValueRef<Volume>;
    coloring: PD.Mapped<PD.NamedParams<PD.Normalize<{
        domain: PD.NamedParams<[number, number], "custom"> | PD.NamedParams<PD.Normalize<{
            symmetric: /*elided*/ any;
        }>, "auto">;
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "absolute-value"> | PD.NamedParams<PD.Normalize<{
        domain: PD.NamedParams<[number, number], "custom"> | PD.NamedParams<PD.Normalize<{
            symmetric: /*elided*/ any;
        }>, "auto">;
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "relative-value">>;
    defaultColor: PD.Color;
    normalOffset: PD.Numeric;
    usePalette: PD.BooleanParam;
};
export type ExternalVolumeColorThemeParams = typeof ExternalVolumeColorThemeParams;
export declare function ExternalVolumeColorTheme(ctx: ThemeDataContext, props: PD.Values<ExternalVolumeColorThemeParams>): ColorTheme<ExternalVolumeColorThemeParams>;
export declare const ExternalVolumeColorThemeProvider: ColorTheme.Provider<ExternalVolumeColorThemeParams, 'external-volume'>;
