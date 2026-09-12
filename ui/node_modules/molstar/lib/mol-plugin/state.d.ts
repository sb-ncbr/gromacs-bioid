/**
 * Copyright (c) 2018-2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author David Sehnal <david.sehnal@gmail.com>
 * @author Alexander Rose <alexander.rose@weirdbyte.de>
 * @author Adam Midlik <midlik@gmail.com>
 */
import { Camera } from '../mol-canvas3d/camera';
import { Canvas3DContext, Canvas3DProps } from '../mol-canvas3d/canvas3d';
import { Vec3 } from '../mol-math/linear-algebra';
import { PluginComponent } from '../mol-plugin-state/component';
import { PluginAnimationManager } from '../mol-plugin-state/manager/animation';
import { InteractivityManager } from '../mol-plugin-state/manager/interactivity';
import { StructureComponentManager } from '../mol-plugin-state/manager/structure/component';
import { StructureFocusSnapshot } from '../mol-plugin-state/manager/structure/focus';
import { StructureSelectionSnapshot } from '../mol-plugin-state/manager/structure/selection';
import { State, StateTransform, StateTransformer } from '../mol-state';
import { UUID } from '../mol-util';
import { ParamDefinition as PD } from '../mol-util/param-definition';
import { PluginContext } from './context';
export { PluginState };
declare class PluginState extends PluginComponent {
    private plugin;
    private get animation();
    readonly data: State;
    readonly behaviors: State;
    readonly events: {
        readonly cell: {
            readonly stateUpdated: import("rxjs").Observable<State.ObjectEvent & {
                cell: import("../mol-state").StateObjectCell;
            }>;
            readonly created: import("rxjs").Observable<State.ObjectEvent & {
                cell: import("../mol-state").StateObjectCell;
            }>;
            readonly removed: import("rxjs").Observable<State.ObjectEvent & {
                parent: StateTransform.Ref;
            }>;
        };
        readonly object: {
            readonly created: import("rxjs").Observable<State.ObjectEvent & {
                obj: import("../mol-state").StateObject;
            }>;
            readonly removed: import("rxjs").Observable<State.ObjectEvent & {
                obj?: import("../mol-state").StateObject;
            }>;
            readonly updated: import("rxjs").Observable<State.ObjectEvent & {
                action: "in-place" | "recreate";
                obj: import("../mol-state").StateObject;
                oldObj?: import("../mol-state").StateObject;
                oldData?: any;
            }>;
        };
    };
    readonly snapshotParams: import("rxjs").BehaviorSubject<Partial<PD.Values<{
        durationInMs: PD.Numeric;
        data: PD.BooleanParam;
        behavior: PD.BooleanParam;
        structureSelection: PD.BooleanParam;
        componentManager: PD.BooleanParam;
        animation: PD.BooleanParam;
        startAnimation: PD.BooleanParam;
        canvas3d: PD.BooleanParam;
        canvas3dContext: PD.BooleanParam;
        interactivity: PD.BooleanParam;
        camera: PD.BooleanParam;
        cameraTransition: PD.Mapped<PD.NamedParams<PD.Normalize<{
            durationInMs: number;
        }>, "animate"> | PD.NamedParams<PD.Normalize<unknown>, "instant">>;
        image: PD.BooleanParam;
    }>>>;
    setSnapshotParams: (params?: PluginState.SnapshotParams) => void;
    getSnapshot(params?: PluginState.SnapshotParams): PluginState.Snapshot;
    setSnapshot(snapshot: PluginState.Snapshot): Promise<void>;
    updateTransform(state: State, a: StateTransform.Ref, params: any, canUndo?: string | boolean): Promise<void>;
    hasBehavior(behavior: StateTransformer): boolean;
    updateBehavior<T extends StateTransformer>(behavior: T, params: (old: StateTransformer.Params<T>) => (void | StateTransformer.Params<T>)): Promise<void>;
    dispose(): void;
    constructor(plugin: PluginContext);
}
declare namespace PluginState {
    type CameraTransitionStyle = 'instant' | 'animate';
    const SnapshotParams: {
        durationInMs: PD.Numeric;
        data: PD.BooleanParam;
        behavior: PD.BooleanParam;
        structureSelection: PD.BooleanParam;
        componentManager: PD.BooleanParam;
        animation: PD.BooleanParam;
        startAnimation: PD.BooleanParam;
        canvas3d: PD.BooleanParam;
        canvas3dContext: PD.BooleanParam;
        interactivity: PD.BooleanParam;
        camera: PD.BooleanParam;
        cameraTransition: PD.Mapped<PD.NamedParams<PD.Normalize<{
            durationInMs: number;
        }>, "animate"> | PD.NamedParams<PD.Normalize<unknown>, "instant">>;
        image: PD.BooleanParam;
    };
    type SnapshotParams = Partial<PD.Values<typeof SnapshotParams>>;
    const DefaultSnapshotParams: PD.Values<{
        durationInMs: PD.Numeric;
        data: PD.BooleanParam;
        behavior: PD.BooleanParam;
        structureSelection: PD.BooleanParam;
        componentManager: PD.BooleanParam;
        animation: PD.BooleanParam;
        startAnimation: PD.BooleanParam;
        canvas3d: PD.BooleanParam;
        canvas3dContext: PD.BooleanParam;
        interactivity: PD.BooleanParam;
        camera: PD.BooleanParam;
        cameraTransition: PD.Mapped<PD.NamedParams<PD.Normalize<{
            durationInMs: number;
        }>, "animate"> | PD.NamedParams<PD.Normalize<unknown>, "instant">>;
        image: PD.BooleanParam;
    }>;
    interface Snapshot {
        id: UUID;
        data?: State.Snapshot;
        behaviour?: State.Snapshot;
        animation?: PluginAnimationManager.Snapshot;
        startAnimation?: boolean;
        camera?: {
            current?: Camera.Snapshot;
            focus?: SnapshotFocusInfo;
            transitionStyle: CameraTransitionStyle;
            transitionDurationInMs?: number;
        };
        canvas3d?: {
            props?: Canvas3DProps;
        };
        canvas3dContext?: {
            props?: Canvas3DContext.Props;
        };
        interactivity?: {
            props?: InteractivityManager.Props;
        };
        structureFocus?: StructureFocusSnapshot;
        structureSelection?: StructureSelectionSnapshot;
        structureComponentManager?: {
            options?: StructureComponentManager.Options;
        };
        durationInMs?: number;
    }
    type SnapshotType = 'json' | 'molj' | 'zip' | 'molx';
    interface SnapshotFocusInfo {
        targets?: SnapshotFocusTargetInfo[];
        direction?: Vec3;
        up?: Vec3;
    }
    /** Final radius to be computed as `radius ?? targetBoundingRadius * radiusFactor + extraRadius` */
    interface SnapshotFocusTargetInfo {
        /** Reference to plugin state node to focus (undefined means focus whole scene) */
        targetRef?: StateTransform.Ref;
        radius?: number;
        radiusFactor?: number;
        extraRadius?: number;
    }
}
