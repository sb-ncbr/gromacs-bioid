/**
 * Copyright (c) 2023-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 */
import { Color } from '../../mol-util/color';
import type { ColorTheme } from '../color';
import { ParamDefinition as PD } from '../../mol-util/param-definition';
import { ThemeDataContext } from '../theme';
export declare const CartoonColorThemeParams: {
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
        scale: "DGwif" | "DGwoct" | "Oct-IF";
    }>, "hydrophobicity"> | PD.NamedParams<PD.Normalize<{
        domain: [number, number];
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "sequence-id"> | PD.NamedParams<PD.Normalize<{
        domain: [number, number];
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "partial-charge">>;
};
export type CartoonColorThemeParams = typeof CartoonColorThemeParams;
export declare function getCartoonColorThemeParams(ctx: ThemeDataContext): {
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
        scale: "DGwif" | "DGwoct" | "Oct-IF";
    }>, "hydrophobicity"> | PD.NamedParams<PD.Normalize<{
        domain: [number, number];
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
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
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "sequence-id"> | PD.NamedParams<PD.Normalize<{
        domain: [number, number];
        list: {
            kind: "interpolate" | "set";
            colors: import("../../mol-util/color/color").ColorListEntry[];
        };
    }>, "partial-charge">>;
};
export declare function CartoonColorTheme(ctx: ThemeDataContext, props: PD.Values<CartoonColorThemeParams>): ColorTheme<CartoonColorThemeParams>;
export declare const CartoonColorThemeProvider: ColorTheme.Provider<CartoonColorThemeParams, 'cartoon'>;
