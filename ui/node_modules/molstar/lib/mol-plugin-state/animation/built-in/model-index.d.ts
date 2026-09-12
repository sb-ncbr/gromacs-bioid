/**
 * Copyright (c) 2019 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 */
import { ParamDefinition as PD } from '../../../mol-util/param-definition';
import { PluginStateAnimation } from '../model';
export declare const AnimateModelIndex: PluginStateAnimation<{
    mode: PD.NamedParams<PD.Normalize<{
        direction: /*elided*/ any;
    }>, "loop"> | PD.NamedParams<PD.Normalize<unknown>, "palindrome"> | PD.NamedParams<PD.Normalize<{
        direction: /*elided*/ any;
    }>, "once">;
    duration: PD.NamedParams<PD.Normalize<{
        durationInS: /*elided*/ any;
    }>, "fixed"> | PD.NamedParams<PD.Normalize<{
        maxFps: /*elided*/ any;
    }>, "sequential"> | PD.NamedParams<PD.Normalize<{
        targetFps: /*elided*/ any;
    }>, "computed">;
}, {
    palindromeDirections?: {
        [id: string]: -1 | 1 | undefined;
    };
}>;
