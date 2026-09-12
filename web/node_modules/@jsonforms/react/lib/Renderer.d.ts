import React from 'react';
import type { RendererProps } from '@jsonforms/core';
/**
 * Convenience wrapper around React's Component for constraining props.
 *
 * @template P type of any renderer props
 * @template S state of the Renderer
 */
export declare class RendererComponent<P extends RendererProps, S = {}> extends React.Component<P, S> {
    constructor(props: P);
}
/**
 * Stateless Renderer.
 *
 * @template P type of any renderer props
 */
export type StatelessRenderer<P extends RendererProps> = React.StatelessComponent<P>;
/**
 * Represents a Renderer, which might either be a component or a function.
 */
export type Renderer = RendererComponent<RendererProps & any, {}> | StatelessRenderer<RendererProps & any>;
