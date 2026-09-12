import React, { Component } from 'react';
/**
 * Props of an {@link UnknownRenderer}
 */
export interface UnknownRendererProps {
    /**
     * The type for which no renderer has been found.
     */
    type: 'renderer' | 'cell';
}
/**
 * A renderer that will be used in case no other renderer is applicable.
 */
export declare class UnknownRenderer extends Component<UnknownRendererProps, any> {
    render(): React.JSX.Element;
}
