import React from 'react';
import { JsonSchema } from '@jsonforms/core';
interface CombinatorPropertiesProps {
    schema: JsonSchema;
    combinatorKeyword: 'oneOf' | 'anyOf';
    path: string;
    rootSchema: JsonSchema;
}
export declare class CombinatorProperties extends React.Component<CombinatorPropertiesProps, {}> {
    render(): React.JSX.Element;
}
export default CombinatorProperties;
