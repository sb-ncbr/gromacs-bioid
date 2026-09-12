/**
 * Copyright (c) 2021-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Mandar Deshpande <mandar@ebi.ac.uk>
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { ColorTheme } from '../../../../mol-theme/color';
import { ThemeDataContext } from '../../../../mol-theme/theme';
import { ParamDefinition as PD } from '../../../../mol-util/param-definition';
export declare function getPLDDTConfidenceColorThemeParams(ctx: ThemeDataContext): {
    metricId: PD.Select<number> | PD.Select<undefined>;
};
export type PLDDTConfidenceColorThemeParams = ReturnType<typeof getPLDDTConfidenceColorThemeParams>;
export declare function PLDDTConfidenceColorTheme(ctx: ThemeDataContext, props: PD.Values<PLDDTConfidenceColorThemeParams>): ColorTheme<PLDDTConfidenceColorThemeParams>;
export declare const PLDDTConfidenceColorThemeProvider: ColorTheme.Provider<PLDDTConfidenceColorThemeParams, 'plddt-confidence'>;
