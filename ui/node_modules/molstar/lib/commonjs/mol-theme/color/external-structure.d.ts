/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Color } from '../../mol-util/color';
import type { ColorTheme } from '../color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../theme';
import { Structure } from '../../mol-model/structure';
export declare const ExternalStructureColorThemeParams: {
    structure: PD.ValueRef<Structure>;
    style: PD.Mapped<PD.NamedParams<PD.Normalize<{
        palette: PD.NamedParams<PD.Normalize<{
            maxCount: /*elided*/ any;
            hue: /*elided*/ any;
            chroma: /*elided*/ any;
            luminance: /*elided*/ any;
            sort: /*elided*/ any;
            clusteringStepCount: /*elided*/ any;
            minSampleCount: /*elided*/ any;
            sampleCountFactor: /*elided*/ any;
        }>, "generate"> | PD.NamedParams<PD.Normalize<{
            list: /*elided*/ any;
        }>, "colors">;
        asymId: "label" | "auth";
    }>, "chain-id"> | PD.NamedParams<PD.Normalize<{
        overrideWater: boolean;
        waterColor: Color;
        palette: PD.NamedParams<PD.Normalize<{
            maxCount: /*elided*/ any;
            hue: /*elided*/ any;
            chroma: /*elided*/ any;
            luminance: /*elided*/ any;
            sort: /*elided*/ any;
            clusteringStepCount: /*elided*/ any;
            minSampleCount: /*elided*/ any;
            sampleCountFactor: /*elided*/ any;
        }>, "generate"> | PD.NamedParams<PD.Normalize<{
            list: /*elided*/ any;
        }>, "colors">;
    }>, "entity-id"> | PD.NamedParams<PD.Normalize<{
        palette: PD.NamedParams<PD.Normalize<{
            maxCount: /*elided*/ any;
            hue: /*elided*/ any;
            chroma: /*elided*/ any;
            luminance: /*elided*/ any;
            sort: /*elided*/ any;
            clusteringStepCount: /*elided*/ any;
            minSampleCount: /*elided*/ any;
            sampleCountFactor: /*elided*/ any;
        }>, "generate"> | PD.NamedParams<PD.Normalize<{
            list: /*elided*/ any;
        }>, "colors">;
    }>, "entity-source"> | PD.NamedParams<PD.Normalize<{
        palette: PD.NamedParams<PD.Normalize<{
            maxCount: /*elided*/ any;
            hue: /*elided*/ any;
            chroma: /*elided*/ any;
            luminance: /*elided*/ any;
            sort: /*elided*/ any;
            clusteringStepCount: /*elided*/ any;
            minSampleCount: /*elided*/ any;
            sampleCountFactor: /*elided*/ any;
        }>, "generate"> | PD.NamedParams<PD.Normalize<{
            list: /*elided*/ any;
        }>, "colors">;
    }>, "model-index"> | PD.NamedParams<PD.Normalize<{
        palette: PD.NamedParams<PD.Normalize<{
            maxCount: /*elided*/ any;
            hue: /*elided*/ any;
            chroma: /*elided*/ any;
            luminance: /*elided*/ any;
            sort: /*elided*/ any;
            clusteringStepCount: /*elided*/ any;
            minSampleCount: /*elided*/ any;
            sampleCountFactor: /*elided*/ any;
        }>, "generate"> | PD.NamedParams<PD.Normalize<{
            list: /*elided*/ any;
        }>, "colors">;
    }>, "structure-index"> | PD.NamedParams<PD.Normalize<{
        saturation: number;
        lightness: number;
        colors: PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
            water: /*elided*/ any;
            ion: /*elided*/ any;
            protein: /*elided*/ any;
            RNA: /*elided*/ any;
            DNA: /*elided*/ any;
            PNA: /*elided*/ any;
            saccharide: /*elided*/ any;
        }>, "custom">;
    }>, "molecule-type">>;
    defaultColor: PD.Color;
    maxDistance: PD.Numeric;
    approxMaxDistance: PD.Numeric;
    normalOffset: PD.Numeric;
    backboneOnly: PD.BooleanParam;
};
export type ExternalStructureColorThemeParams = typeof ExternalStructureColorThemeParams;
export declare function ExternalStructureColorTheme(ctx: ThemeDataContext, props: PD.Values<ExternalStructureColorThemeParams>): ColorTheme<ExternalStructureColorThemeParams>;
export declare const ExternalStructureColorThemeProvider: ColorTheme.Provider<ExternalStructureColorThemeParams, 'external-structure'>;
