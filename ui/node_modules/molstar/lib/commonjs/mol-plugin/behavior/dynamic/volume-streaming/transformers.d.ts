/**
 * Copyright (c) 2019-2022 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { PluginStateObject as SO } from '../../../../mol-plugin-state/objects';
import { VolumeServerInfo } from './model';
import { ParamDefinition as PD } from '../../../../mol-util/param-definition';
import { StateAction, StateTransformer } from '../../../../mol-state';
import { VolumeStreaming } from './behavior';
export declare const InitVolumeStreaming: StateAction<SO.Molecule.Structure, void, PD.Normalize<{
    method: VolumeServerInfo.Kind;
    entries: PD.Normalize<{
        id: string;
    }>[];
    defaultView: VolumeStreaming.ViewTypes;
    options: PD.Normalize<{
        serverUrl: /*elided*/ any;
        behaviorRef: /*elided*/ any;
        emContourProvider: /*elided*/ any;
        channelParams: /*elided*/ any;
    }>;
}>>;
export declare const BoxifyVolumeStreaming: StateAction<VolumeStreaming, void | undefined, PD.Normalize<{}>>;
export { CreateVolumeStreamingInfo };
type CreateVolumeStreamingInfo = typeof CreateVolumeStreamingInfo;
declare const CreateVolumeStreamingInfo: StateTransformer<SO.Molecule.Structure, VolumeServerInfo, PD.Normalize<{
    serverUrl: string;
    entries: PD.Normalize<PD.Values<{
        dataId: PD.Text<string>;
        source: PD.Mapped<PD.NamedParams<PD.Normalize<{
            isoValue: /*elided*/ any;
        }>, "em"> | PD.NamedParams<PD.Normalize<unknown>, "x-ray">>;
    }>>[];
}>>;
export { CreateVolumeStreamingBehavior };
type CreateVolumeStreamingBehavior = typeof CreateVolumeStreamingBehavior;
declare const CreateVolumeStreamingBehavior: StateTransformer<VolumeServerInfo, VolumeStreaming, PD.Normalize<{
    entry: PD.NamedParams<PD.Values<{
        view: PD.Mapped<PD.NamedParams<PD.Normalize<{
            radius: /*elided*/ any;
            selectionDetailLevel: /*elided*/ any;
            isSelection: /*elided*/ any;
            bottomLeft: /*elided*/ any;
            topRight: /*elided*/ any;
        }>, "auto"> | PD.NamedParams<PD.Normalize<{}>, "cell"> | PD.NamedParams<PD.Normalize<{}>, "off"> | PD.NamedParams<PD.Normalize<{
            bottomLeft: /*elided*/ any;
            topRight: /*elided*/ any;
        }>, "box"> | PD.NamedParams<PD.Normalize<{
            radius: /*elided*/ any;
            dynamicDetailLevel: /*elided*/ any;
            bottomLeft: /*elided*/ any;
            topRight: /*elided*/ any;
        }>, "camera-target"> | PD.NamedParams<PD.Normalize<{
            radius: /*elided*/ any;
            bottomLeft: /*elided*/ any;
            topRight: /*elided*/ any;
        }>, "selection-box">>;
        detailLevel: PD.Select<number>;
        channels: PD.Group<PD.Normalize<{
            em: /*elided*/ any;
        }>> | PD.Group<PD.Normalize<{
            '2fo-fc': /*elided*/ any;
            'fo-fc(+ve)': /*elided*/ any;
            'fo-fc(-ve)': /*elided*/ any;
        }>>;
    }>, string>;
}>>;
export { VolumeStreamingVisual };
type VolumeStreamingVisual = typeof VolumeStreamingVisual;
declare const VolumeStreamingVisual: StateTransformer<VolumeStreaming, SO.Volume.Representation3D, PD.Normalize<{
    channel: VolumeStreaming.ChannelType;
}>>;
