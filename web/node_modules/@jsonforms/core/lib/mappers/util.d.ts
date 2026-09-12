import { JsonSchema, UISchemaElement } from '../models';
import { JsonFormsState } from '../store';
/**
 * Indicates whether the given `uischema` element shall be enabled or disabled.
 * Checks the global readonly flag, uischema rule, uischema options (including the config),
 * the schema and the enablement indicator of the parent.
 */
export declare const isInherentlyEnabled: (state: JsonFormsState, ownProps: any, uischema: UISchemaElement, schema: (JsonSchema & {
    readOnly?: boolean;
}) | undefined, rootData: any, config: any) => any;
