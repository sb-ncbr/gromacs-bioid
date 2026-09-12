import { RendererComponent } from './Renderer';
import type { ControlProps, ControlState } from '@jsonforms/core';
/**
 * A controlled component convenience wrapper that additionally manages a focused state.
 *
 * @template P control specific properties
 * @template S the state managed by the control
 */
export declare class Control<P extends ControlProps, S extends ControlState> extends RendererComponent<P, S> {
    constructor(props: P);
    /**
     * Propagates a value change.
     *
     * @param value the updated value
     */
    handleChange: (value: any) => void;
    /**
     * Set the focused state to true.
     */
    onFocus: () => void;
    /**
     * Set the focused state to false.
     */
    onBlur: () => void;
    private updateData;
}
