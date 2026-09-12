/**
 * Copyright (c) 2018-2025 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Color } from '../mol-util/color';
import { Location } from '../mol-model/location';
import { ColorType, ColorTypeDirect, ColorTypeGrid, ColorTypeLocation } from '../mol-geo/geometry/color-data';
import { ParamDefinition as PD } from '../mol-util/param-definition';
import { ThemeDataContext, ThemeRegistry, ThemeProvider } from './theme';
import { ScaleLegend, TableLegend } from '../mol-util/legend';
import type { Texture, TextureFilter } from '../mol-gl/webgl/texture';
import { Vec3, Vec4 } from '../mol-math/linear-algebra';
import { ColorListEntry } from '../mol-util/color/color';
export type LocationColor = (location: Location, isSecondary: boolean) => Color;
export interface ColorVolume {
    colors: Texture;
    dimension: Vec3;
    transform: Vec4;
}
export { ColorTheme };
type ColorThemeShared<P extends PD.Params, G extends ColorType> = {
    readonly factory: ColorTheme.Factory<P, G>;
    readonly props: Readonly<PD.Values<P>>;
    /**
     * if palette is defined, 24bit RGB color value normalized to interval [0, 1]
     * is used as index to the colors
     */
    readonly palette?: Readonly<ColorTheme.Palette>;
    readonly preferSmoothing?: boolean;
    readonly contextHash?: number;
    readonly description?: string;
    readonly legend?: Readonly<ScaleLegend | TableLegend>;
};
type ColorThemeLocation<P extends PD.Params> = {
    readonly granularity: ColorTypeLocation;
    readonly color: LocationColor;
} & ColorThemeShared<P, ColorTypeLocation>;
type ColorThemeGrid<P extends PD.Params> = {
    readonly granularity: ColorTypeGrid;
    readonly grid: ColorVolume;
} & ColorThemeShared<P, ColorTypeGrid>;
type ColorThemeDirect<P extends PD.Params> = {
    readonly granularity: ColorTypeDirect;
} & ColorThemeShared<P, ColorTypeDirect>;
type ColorTheme<P extends PD.Params, G extends ColorType = ColorTypeLocation> = G extends ColorTypeLocation ? ColorThemeLocation<P> : G extends ColorTypeGrid ? ColorThemeGrid<P> : G extends ColorTypeDirect ? ColorThemeDirect<P> : never;
declare namespace ColorTheme {
    export const Category: {
        Atom: string;
        Chain: string;
        Residue: string;
        Symmetry: string;
        Validation: string;
        Misc: string;
    };
    export interface Palette {
        colors: Color[];
        filter?: TextureFilter;
        domain?: [number, number];
        defaultColor?: Color;
    }
    export function Palette(list: ColorListEntry[], kind: 'set' | 'interpolate', domain?: [number, number], defaultColor?: Color): Palette;
    export const PaletteScale: number;
    export type Props = {
        [k: string]: any;
    };
    export type Factory<P extends PD.Params, G extends ColorType> = (ctx: ThemeDataContext, props: PD.Values<P>) => ColorTheme<P, G>;
    export const EmptyFactory: () => ColorThemeLocation<{}>;
    export const Empty: ColorTheme<{}>;
    export function areEqual(themeA: ColorTheme<any, any>, themeB: ColorTheme<any, any>): boolean;
    export interface Provider<P extends PD.Params = any, Id extends string = string, G extends ColorType = ColorType> extends ThemeProvider<ColorTheme<P, G>, P, Id, G> {
    }
    export const EmptyProvider: Provider<{}>;
    export type Registry = ThemeRegistry<ColorTheme<any, any>>;
    export function createRegistry(): ThemeRegistry<ColorThemeLocation<{}> | ColorThemeDirect<{}> | ColorThemeGrid<{}>>;
    export const BuiltIn: {
        'atom-id': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "atom-id", ColorType>;
        'carbohydrate-symbol': Provider<{}, "carbohydrate-symbol", ColorType>;
        cartoon: Provider<{
            mainchain: PD.Mapped<PD.NamedParams<PD.Normalize<{
                value: Color;
                saturation: number;
                lightness: number;
            }>, "uniform"> | PD.NamedParams<PD.Normalize<{
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
            }>, "trajectory-index"> | PD.NamedParams<PD.Normalize<{
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
            }>, "molecule-type"> | PD.NamedParams<PD.Normalize<{
                saturation: number;
                lightness: number;
                colors: PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                    alphaHelix: /*elided*/ any;
                    threeTenHelix: /*elided*/ any;
                    piHelix: /*elided*/ any;
                    betaTurn: /*elided*/ any;
                    betaStrand: /*elided*/ any;
                    coil: /*elided*/ any;
                    bend: /*elided*/ any;
                    turn: /*elided*/ any;
                    dna: /*elided*/ any;
                    rna: /*elided*/ any;
                    carbohydrate: /*elided*/ any;
                }>, "custom">;
            }>, "secondary-structure">>;
            sidechain: PD.Mapped<PD.NamedParams<PD.Normalize<{
                value: Color;
                saturation: number;
                lightness: number;
            }>, "uniform"> | PD.NamedParams<PD.Normalize<{
                domain: [number, number];
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "occupancy"> | PD.NamedParams<PD.Normalize<{
                carbonColor: PD.NamedParams<PD.Normalize<{
                    value: /*elided*/ any;
                    saturation: /*elided*/ any;
                    lightness: /*elided*/ any;
                }>, "uniform"> | PD.NamedParams<PD.Normalize<unknown>, "element-symbol"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                    asymId: /*elided*/ any;
                }>, "chain-id"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "operator-name"> | PD.NamedParams<PD.Normalize<{
                    overrideWater: /*elided*/ any;
                    waterColor: /*elided*/ any;
                    palette: /*elided*/ any;
                }>, "entity-id"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "entity-source"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "model-index"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "structure-index"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "unit-index"> | PD.NamedParams<PD.Normalize<{
                    palette: /*elided*/ any;
                }>, "trajectory-index">;
                saturation: number;
                lightness: number;
                colors: PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                    H: /*elided*/ any;
                    D: /*elided*/ any;
                    T: /*elided*/ any;
                    HE: /*elided*/ any;
                    LI: /*elided*/ any;
                    BE: /*elided*/ any;
                    B: /*elided*/ any;
                    C: /*elided*/ any;
                    N: /*elided*/ any;
                    O: /*elided*/ any;
                    F: /*elided*/ any;
                    NE: /*elided*/ any;
                    NA: /*elided*/ any;
                    MG: /*elided*/ any;
                    AL: /*elided*/ any;
                    SI: /*elided*/ any;
                    P: /*elided*/ any;
                    S: /*elided*/ any;
                    CL: /*elided*/ any;
                    AR: /*elided*/ any;
                    K: /*elided*/ any;
                    CA: /*elided*/ any;
                    SC: /*elided*/ any;
                    TI: /*elided*/ any;
                    V: /*elided*/ any;
                    CR: /*elided*/ any;
                    MN: /*elided*/ any;
                    FE: /*elided*/ any;
                    CO: /*elided*/ any;
                    NI: /*elided*/ any;
                    CU: /*elided*/ any;
                    ZN: /*elided*/ any;
                    GA: /*elided*/ any;
                    GE: /*elided*/ any;
                    AS: /*elided*/ any;
                    SE: /*elided*/ any;
                    BR: /*elided*/ any;
                    KR: /*elided*/ any;
                    RB: /*elided*/ any;
                    SR: /*elided*/ any;
                    Y: /*elided*/ any;
                    ZR: /*elided*/ any;
                    NB: /*elided*/ any;
                    MO: /*elided*/ any;
                    TC: /*elided*/ any;
                    RU: /*elided*/ any;
                    RH: /*elided*/ any;
                    PD: /*elided*/ any;
                    AG: /*elided*/ any;
                    CD: /*elided*/ any;
                    IN: /*elided*/ any;
                    SN: /*elided*/ any;
                    SB: /*elided*/ any;
                    TE: /*elided*/ any;
                    I: /*elided*/ any;
                    XE: /*elided*/ any;
                    CS: /*elided*/ any;
                    BA: /*elided*/ any;
                    LA: /*elided*/ any;
                    CE: /*elided*/ any;
                    PR: /*elided*/ any;
                    ND: /*elided*/ any;
                    PM: /*elided*/ any;
                    SM: /*elided*/ any;
                    EU: /*elided*/ any;
                    GD: /*elided*/ any;
                    TB: /*elided*/ any;
                    DY: /*elided*/ any;
                    HO: /*elided*/ any;
                    ER: /*elided*/ any;
                    TM: /*elided*/ any;
                    YB: /*elided*/ any;
                    LU: /*elided*/ any;
                    HF: /*elided*/ any;
                    TA: /*elided*/ any;
                    W: /*elided*/ any;
                    RE: /*elided*/ any;
                    OS: /*elided*/ any;
                    IR: /*elided*/ any;
                    PT: /*elided*/ any;
                    AU: /*elided*/ any;
                    HG: /*elided*/ any;
                    TL: /*elided*/ any;
                    PB: /*elided*/ any;
                    BI: /*elided*/ any;
                    PO: /*elided*/ any;
                    AT: /*elided*/ any;
                    RN: /*elided*/ any;
                    FR: /*elided*/ any;
                    RA: /*elided*/ any;
                    AC: /*elided*/ any;
                    TH: /*elided*/ any;
                    PA: /*elided*/ any;
                    U: /*elided*/ any;
                    NP: /*elided*/ any;
                    PU: /*elided*/ any;
                    AM: /*elided*/ any;
                    CM: /*elided*/ any;
                    BK: /*elided*/ any;
                    CF: /*elided*/ any;
                    ES: /*elided*/ any;
                    FM: /*elided*/ any;
                    MD: /*elided*/ any;
                    NO: /*elided*/ any;
                    LR: /*elided*/ any;
                    RF: /*elided*/ any;
                    DB: /*elided*/ any;
                    SG: /*elided*/ any;
                    BH: /*elided*/ any;
                    HS: /*elided*/ any;
                    MT: /*elided*/ any;
                    DS: /*elided*/ any;
                    RG: /*elided*/ any;
                    CN: /*elided*/ any;
                    UUT: /*elided*/ any;
                    FL: /*elided*/ any;
                    UUP: /*elided*/ any;
                    LV: /*elided*/ any;
                    UUH: /*elided*/ any;
                }>, "custom">;
            }>, "element-symbol"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
                scale: "DGwif" | "DGwoct" | "Oct-IF";
            }>, "hydrophobicity"> | PD.NamedParams<PD.Normalize<{
                domain: [number, number];
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "uncertainty"> | PD.NamedParams<PD.Normalize<{
                saturation: number;
                lightness: number;
                colors: PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                    ALA: /*elided*/ any;
                    ARG: /*elided*/ any;
                    ASN: /*elided*/ any;
                    ASP: /*elided*/ any;
                    CYS: /*elided*/ any;
                    GLN: /*elided*/ any;
                    GLU: /*elided*/ any;
                    GLY: /*elided*/ any;
                    HIS: /*elided*/ any;
                    ILE: /*elided*/ any;
                    LEU: /*elided*/ any;
                    LYS: /*elided*/ any;
                    MET: /*elided*/ any;
                    PHE: /*elided*/ any;
                    PRO: /*elided*/ any;
                    SER: /*elided*/ any;
                    THR: /*elided*/ any;
                    TRP: /*elided*/ any;
                    TYR: /*elided*/ any;
                    VAL: /*elided*/ any;
                    A: /*elided*/ any;
                    G: /*elided*/ any;
                    I: /*elided*/ any;
                    C: /*elided*/ any;
                    T: /*elided*/ any;
                    U: /*elided*/ any;
                    DA: /*elided*/ any;
                    DG: /*elided*/ any;
                    DI: /*elided*/ any;
                    DC: /*elided*/ any;
                    DT: /*elided*/ any;
                    DU: /*elided*/ any;
                    APN: /*elided*/ any;
                    GPN: /*elided*/ any;
                    CPN: /*elided*/ any;
                    TPN: /*elided*/ any;
                }>, "custom">;
            }>, "residue-name"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "sequence-id"> | PD.NamedParams<PD.Normalize<{
                domain: [number, number];
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "partial-charge">>;
        }, "cartoon", ColorType>;
        'chain-id': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
            asymId: PD.Select<"label" | "auth">;
        }, "chain-id", ColorType>;
        'element-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "element-index", ColorType>;
        'element-symbol': Provider<{
            carbonColor: PD.Mapped<PD.NamedParams<PD.Normalize<{
                value: Color;
                saturation: number;
                lightness: number;
            }>, "uniform"> | PD.NamedParams<PD.Normalize<unknown>, "element-symbol"> | PD.NamedParams<PD.Normalize<{
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
            }>, "operator-name"> | PD.NamedParams<PD.Normalize<{
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
            }>, "unit-index"> | PD.NamedParams<PD.Normalize<{
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
            }>, "trajectory-index">>;
            saturation: PD.Numeric;
            lightness: PD.Numeric;
            colors: PD.Mapped<PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                H: Color;
                D: Color;
                T: Color;
                HE: Color;
                LI: Color;
                BE: Color;
                B: Color;
                C: Color;
                N: Color;
                O: Color;
                F: Color;
                NE: Color;
                NA: Color;
                MG: Color;
                AL: Color;
                SI: Color;
                P: Color;
                S: Color;
                CL: Color;
                AR: Color;
                K: Color;
                CA: Color;
                SC: Color;
                TI: Color;
                V: Color;
                CR: Color;
                MN: Color;
                FE: Color;
                CO: Color;
                NI: Color;
                CU: Color;
                ZN: Color;
                GA: Color;
                GE: Color;
                AS: Color;
                SE: Color;
                BR: Color;
                KR: Color;
                RB: Color;
                SR: Color;
                Y: Color;
                ZR: Color;
                NB: Color;
                MO: Color;
                TC: Color;
                RU: Color;
                RH: Color;
                PD: Color;
                AG: Color;
                CD: Color;
                IN: Color;
                SN: Color;
                SB: Color;
                TE: Color;
                I: Color;
                XE: Color;
                CS: Color;
                BA: Color;
                LA: Color;
                CE: Color;
                PR: Color;
                ND: Color;
                PM: Color;
                SM: Color;
                EU: Color;
                GD: Color;
                TB: Color;
                DY: Color;
                HO: Color;
                ER: Color;
                TM: Color;
                YB: Color;
                LU: Color;
                HF: Color;
                TA: Color;
                W: Color;
                RE: Color;
                OS: Color;
                IR: Color;
                PT: Color;
                AU: Color;
                HG: Color;
                TL: Color;
                PB: Color;
                BI: Color;
                PO: Color;
                AT: Color;
                RN: Color;
                FR: Color;
                RA: Color;
                AC: Color;
                TH: Color;
                PA: Color;
                U: Color;
                NP: Color;
                PU: Color;
                AM: Color;
                CM: Color;
                BK: Color;
                CF: Color;
                ES: Color;
                FM: Color;
                MD: Color;
                NO: Color;
                LR: Color;
                RF: Color;
                DB: Color;
                SG: Color;
                BH: Color;
                HS: Color;
                MT: Color;
                DS: Color;
                RG: Color;
                CN: Color;
                UUT: Color;
                FL: Color;
                UUP: Color;
                LV: Color;
                UUH: Color;
            }>, "custom">>;
        }, "element-symbol", ColorType>;
        'entity-id': Provider<{
            overrideWater: PD.BooleanParam;
            waterColor: PD.Color;
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "entity-id", ColorType>;
        'entity-source': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "entity-source", ColorType>;
        'external-structure': Provider<{
            structure: PD.ValueRef<import("../mol-model/structure").Structure>;
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
        }, "external-structure", ColorType>;
        'external-volume': Provider<{
            volume: PD.ValueRef<import("../mol-model/volume").Volume>;
            coloring: PD.Mapped<PD.NamedParams<PD.Normalize<{
                domain: PD.NamedParams<[number, number], "custom"> | PD.NamedParams<PD.Normalize<{
                    symmetric: /*elided*/ any;
                }>, "auto">;
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "absolute-value"> | PD.NamedParams<PD.Normalize<{
                domain: PD.NamedParams<[number, number], "custom"> | PD.NamedParams<PD.Normalize<{
                    symmetric: /*elided*/ any;
                }>, "auto">;
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "relative-value">>;
            defaultColor: PD.Color;
            normalOffset: PD.Numeric;
            usePalette: PD.BooleanParam;
        }, "external-volume", ColorType>;
        'formal-charge': Provider<{
            domain: PD.Interval;
            list: PD.ColorList;
        }, "formal-charge", ColorType>;
        hydrophobicity: Provider<{
            list: PD.ColorList;
            scale: PD.Select<"DGwif" | "DGwoct" | "Oct-IF">;
        }, "hydrophobicity", ColorType>;
        illustrative: Provider<{
            style: PD.Mapped<PD.NamedParams<PD.Normalize<{
                value: Color;
                saturation: number;
                lightness: number;
            }>, "uniform"> | PD.NamedParams<PD.Normalize<{
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
            }>, "trajectory-index"> | PD.NamedParams<PD.Normalize<{
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
            carbonLightness: PD.Numeric;
        }, "illustrative", ColorType>;
        'model-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "model-index", ColorType>;
        'molecule-type': Provider<{
            saturation: PD.Numeric;
            lightness: PD.Numeric;
            colors: PD.Mapped<PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                water: Color;
                ion: Color;
                protein: Color;
                RNA: Color;
                DNA: Color;
                PNA: Color;
                saccharide: Color;
            }>, "custom">>;
        }, "molecule-type", ColorType>;
        occupancy: Provider<{
            domain: PD.Interval;
            list: PD.ColorList;
        }, "occupancy", ColorType>;
        'operator-hkl': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "operator-hkl", ColorType>;
        'operator-name': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "operator-name", ColorType>;
        'partial-charge': Provider<{
            domain: PD.Interval;
            list: PD.ColorList;
        }, "partial-charge", ColorType>;
        'polymer-id': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "polymer-id", ColorType>;
        'polymer-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "polymer-index", ColorType>;
        'residue-name': Provider<{
            saturation: PD.Numeric;
            lightness: PD.Numeric;
            colors: PD.Mapped<PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                ALA: Color;
                ARG: Color;
                ASN: Color;
                ASP: Color;
                CYS: Color;
                GLN: Color;
                GLU: Color;
                GLY: Color;
                HIS: Color;
                ILE: Color;
                LEU: Color;
                LYS: Color;
                MET: Color;
                PHE: Color;
                PRO: Color;
                SER: Color;
                THR: Color;
                TRP: Color;
                TYR: Color;
                VAL: Color;
                A: Color;
                G: Color;
                I: Color;
                C: Color;
                T: Color;
                U: Color;
                DA: Color;
                DG: Color;
                DI: Color;
                DC: Color;
                DT: Color;
                DU: Color;
                APN: Color;
                GPN: Color;
                CPN: Color;
                TPN: Color;
            }>, "custom">>;
        }, "residue-name", ColorType>;
        'secondary-structure': Provider<{
            saturation: PD.Numeric;
            lightness: PD.Numeric;
            colors: PD.Mapped<PD.NamedParams<PD.Normalize<unknown>, "default"> | PD.NamedParams<PD.Normalize<{
                alphaHelix: Color;
                threeTenHelix: Color;
                piHelix: Color;
                betaTurn: Color;
                betaStrand: Color;
                coil: Color;
                bend: Color;
                turn: Color;
                dna: Color;
                rna: Color;
                carbohydrate: Color;
            }>, "custom">>;
        }, "secondary-structure", ColorType>;
        'sequence-id': Provider<{
            list: PD.ColorList;
        }, "sequence-id", ColorType>;
        'shape-group': Provider<{}, "shape-group", ColorType>;
        'structure-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "structure-index", ColorType>;
        'trajectory-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "trajectory-index", ColorType>;
        uncertainty: Provider<{
            domain: PD.Interval;
            list: PD.ColorList;
        }, "uncertainty", ColorType>;
        'unit-index': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "unit-index", ColorType>;
        uniform: Provider<{
            value: PD.Color;
            saturation: PD.Numeric;
            lightness: PD.Numeric;
        }, "uniform", ColorType>;
        'volume-segment': Provider<{
            palette: PD.Mapped<PD.NamedParams<PD.Normalize<{
                maxCount: number;
                hue: [number, number];
                chroma: [number, number];
                luminance: [number, number];
                sort: "none" | "contrast";
                clusteringStepCount: number;
                minSampleCount: number;
                sampleCountFactor: number;
            }>, "generate"> | PD.NamedParams<PD.Normalize<{
                list: {
                    kind: "interpolate" | "set";
                    colors: ColorListEntry[];
                };
            }>, "colors">>;
        }, "volume-segment", ColorType>;
        'volume-value': Provider<{
            colorList: PD.ColorList;
            domain: PD.Mapped<PD.NamedParams<PD.Normalize<{
                symmetric: boolean;
            }>, "auto"> | PD.NamedParams<[number, number], "custom">>;
            isRelative: PD.BooleanParam;
            defaultColor: PD.Color;
        }, "volume-value", ColorType>;
    };
    type _BuiltIn = typeof BuiltIn;
    export type BuiltIn = keyof _BuiltIn;
    export type ParamValues<C extends ColorTheme.Provider<any>> = C extends ColorTheme.Provider<infer P> ? PD.Values<P> : never;
    export type BuiltInParams<T extends BuiltIn> = Partial<ParamValues<_BuiltIn[T]>>;
    export {};
}
export declare function ColorThemeProvider<P extends PD.Params, Id extends string>(p: ColorTheme.Provider<P, Id>): ColorTheme.Provider<P, Id>;
