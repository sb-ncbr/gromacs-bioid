import { ControlElement, JsonSchema, LabelElement, UISchemaElement } from '../models';
import type { RankedTester } from '../testers';
import { CoreActions } from '../actions';
import type { ErrorObject } from 'ajv';
import type { AnyAction, Dispatch, JsonFormsCellRendererRegistryEntry, JsonFormsRendererRegistryEntry, JsonFormsState, JsonFormsUISchemaRegistryEntry } from '../store';
import { ArrayTranslations } from '../i18n';
import { Translator } from '../store';
import { CombinatorKeyword } from './combinators';
export declare const moveUp: (array: any[], toMove: number) => void;
export declare const moveDown: (array: any[], toMove: number) => void;
/**
 * Adds an asterisk to the given label string based
 * on the required parameter.
 *
 * @param {string | undefined} label the label string
 * @param {boolean} required whether the label belongs to a control which is required
 * @param {boolean} hideRequiredAsterisk applied UI Schema option
 * @returns {string} the label string
 */
export declare const computeLabel: (label: string | undefined, required: boolean, hideRequiredAsterisk: boolean) => string;
/**
 * Indicates whether to mark a field as required.
 *
 * @param {boolean} required whether the label belongs to a control which is required
 * @param {boolean} hideRequiredAsterisk applied UI Schema option
 * @returns {boolean} should the field be marked as required
 */
export declare const showAsRequired: (required: boolean, hideRequiredAsterisk: boolean) => boolean;
/**
 * Create a default value based on the given schema.
 * @param schema the schema for which to create a default value.
 * @returns {any}
 */
export declare const createDefaultValue: (schema: JsonSchema, rootSchema: JsonSchema) => any;
/**
 * Create a default value based on the given schema.
 * @param schema the schema for which to create a default value.
 * @returns the default value to use, undefined if none was found
 */
export declare const doCreateDefaultValue: (schema: JsonSchema, rootSchema: JsonSchema) => any;
/**
 * Returns the default value defined in the given schema.
 * @param schema the schema for which to create a default value.
 * @returns {any}
 */
export declare const extractDefaults: (schema: JsonSchema, rootSchema: JsonSchema) => any;
/**
 * Whether an element's description should be hidden.
 *
 * @param visible whether an element is visible
 * @param description the element's description
 * @param isFocused whether the element is focused
 *
 * @returns {boolean} true, if the description is to be hidden, false otherwise
 */
export declare const isDescriptionHidden: (visible: boolean, description: string | undefined, isFocused: boolean, showUnfocusedDescription: boolean) => boolean;
export interface WithClassname {
    className?: string;
}
export interface EnumOption {
    label: string;
    value: any;
}
export declare const enumToEnumOptionMapper: (e: any, t?: Translator, i18nKey?: string) => EnumOption;
export declare const oneOfToEnumOptionMapper: (e: any, t?: Translator, fallbackI18nKey?: string) => EnumOption;
export interface OwnPropsOfRenderer {
    /**
     * The UI schema to be rendered.
     */
    uischema?: UISchemaElement;
    /**
     * The JSON schema that describes the data.
     */
    schema?: JsonSchema;
    /**
     * Whether the rendered element should be enabled.
     */
    enabled?: boolean;
    /**
     * Whether the rendered element should be visible.
     */
    visible?: boolean;
    /**
     * Optional instance path. Necessary when the actual data
     * path can not be inferred via the UI schema element as
     * it is the case with nested controls.
     */
    path?: string;
    renderers?: JsonFormsRendererRegistryEntry[];
    cells?: JsonFormsCellRendererRegistryEntry[];
    uischemas?: JsonFormsUISchemaRegistryEntry[];
}
export interface OwnPropsOfControl extends OwnPropsOfRenderer {
    id?: string;
    uischema?: ControlElement;
}
export interface OwnPropsOfLabel extends OwnPropsOfRenderer {
    uischema?: LabelElement;
}
export interface OwnPropsOfEnum {
    options?: EnumOption[];
}
export interface OwnPropsOfLayout extends OwnPropsOfRenderer {
    direction?: 'row' | 'column';
}
/**
 * State-based props of a {@link Renderer}.
 */
export interface StatePropsOfRenderer {
    /**
     * Any configuration options for the element.
     */
    config?: any;
    /**
     * The UI schema to be rendered.
     */
    uischema: UISchemaElement;
    /**
     * The JSON schema that describes the data.
     */
    schema: JsonSchema;
    /**
     * The data to be rendered.
     */
    data?: any;
    /**
     * Whether the rendered element should be enabled.
     */
    enabled: boolean;
    /**
     * Whether the rendered element should be visible.
     */
    visible: boolean;
    /**
     * Instance path the data is written to, in case of a control.
     */
    path: string;
    /**
     * All available renderers.
     */
    renderers?: JsonFormsRendererRegistryEntry[];
    /**
     * All available cell renderers.
     */
    cells?: JsonFormsCellRendererRegistryEntry[];
}
/**
 * State-based properties for UI schema elements that have a scope.
 */
export interface StatePropsOfScopedRenderer extends StatePropsOfRenderer {
    uischema: ControlElement;
    /**
     * Any validation errors that are caused by the data to be rendered.
     */
    errors: string;
    /**
     * The data to be rendered.
     */
    data: any;
    /**
     * The root schema as returned by the store.
     */
    rootSchema: JsonSchema;
    /**
     * A unique ID that should be used for rendering the scoped UI schema element.
     */
    id: string;
}
/**
 * Props of a {@link Renderer}.
 */
export interface RendererProps extends StatePropsOfRenderer {
}
/**
 * State-based props of a Control
 */
export interface StatePropsOfControl extends StatePropsOfScopedRenderer {
    cells?: {
        tester: RankedTester;
        cell: any;
    }[];
    /**
     * The label for the rendered element.
     */
    label: string;
    /**
     * Description of input cell
     */
    description?: string;
    /**
     * Whether the rendered data is required.
     */
    required?: boolean;
    i18nKeyPrefix?: string;
}
/**
 * Dispatch-based props of a Control.
 */
export interface DispatchPropsOfControl {
    /**
     * Update handler that emits a data change
     *
     * @param {string} path the path to the data to be updated
     * @param {any} value the new value that should be written to the given path
     */
    handleChange(path: string, value: any): void;
}
/**
 * Props of a Control.
 */
export interface ControlProps extends StatePropsOfControl, DispatchPropsOfControl {
}
/**
 * State props of a layout;
 */
export interface StatePropsOfLayout extends StatePropsOfRenderer {
    /**
     * Direction for the layout to flow
     */
    direction: 'row' | 'column';
    label?: string;
}
export interface LayoutProps extends StatePropsOfLayout {
}
/**
 * The state of a control.
 */
export interface ControlState {
    /**
     * The current value.
     */
    value: any;
    /**
     * Whether the control is focused.
     */
    isFocused: boolean;
}
/**
 * Map state to control props.
 * @param state the store's state
 * @param ownProps any own props
 * @returns {StatePropsOfControl} state props for a control
 */
export declare const mapStateToControlProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfControl;
/**
 *
 * Map dispatch to control props.
 *
 * @param dispatch the store's dispatch method
 * @returns {DispatchPropsOfControl} dispatch props for a control
 */
export declare const mapDispatchToControlProps: (dispatch: Dispatch<AnyAction>) => DispatchPropsOfControl;
/**
 * Default mapStateToCellProps for enum control. Options is used for populating dropdown list
 * @param state
 * @param ownProps
 * @returns {StatePropsOfControl & OwnPropsOfEnum}
 */
export declare const mapStateToEnumControlProps: (state: JsonFormsState, ownProps: OwnPropsOfControl & OwnPropsOfEnum) => StatePropsOfControl & OwnPropsOfEnum;
/**
 * Default mapStateToCellProps for enum control based on oneOf. Options is used for populating dropdown list
 * @param state
 * @param ownProps
 * @returns {StatePropsOfControl & OwnPropsOfEnum}
 */
export declare const mapStateToOneOfEnumControlProps: (state: JsonFormsState, ownProps: OwnPropsOfControl & OwnPropsOfEnum) => StatePropsOfControl & OwnPropsOfEnum;
/**
 * Default mapStateToCellProps for multi enum control. Options is used for populating dropdown list
 * @param state
 * @param ownProps
 * @returns {StatePropsOfControl & OwnPropsOfEnum}
 */
export declare const mapStateToMultiEnumControlProps: (state: JsonFormsState, ownProps: OwnPropsOfControl & OwnPropsOfEnum) => StatePropsOfControl & OwnPropsOfEnum;
/**
 * Map state to control props.
 * @param state the store's state
 * @param ownProps any own props
 * @returns {StatePropsOfControl} state props for a control
 */
export declare const mapStateToMasterListItemProps: (state: JsonFormsState, ownProps: OwnPropsOfMasterListItem) => StatePropsOfMasterItem;
/**
 * State-based props of a table control.
 */
export interface StatePropsOfControlWithDetail extends StatePropsOfControl {
    uischemas?: JsonFormsUISchemaRegistryEntry[];
    renderers?: JsonFormsRendererRegistryEntry[];
    cells?: JsonFormsCellRendererRegistryEntry[];
}
export interface OwnPropsOfMasterListItem {
    index: number;
    selected: boolean;
    path: string;
    enabled: boolean;
    schema: JsonSchema;
    uischema: UISchemaElement;
    childLabelProp?: string;
    handleSelect(index: number): () => void;
    removeItem(path: string, value: number): () => void;
    translations: ArrayTranslations;
    disableRemove?: boolean;
}
export interface StatePropsOfMasterItem extends OwnPropsOfMasterListItem {
    childLabel: string;
}
/**
 * Map state to control with detail props
 *
 * @param state the store's state
 * @param ownProps any element's own props
 * @returns {StatePropsOfArrayControl} state props for a table control
 */
export declare const mapStateToControlWithDetailProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfControlWithDetail;
export interface ControlWithDetailProps extends StatePropsOfControlWithDetail, DispatchPropsOfControl {
}
/**
 * State-based props of a table control.
 */
export interface StatePropsOfArrayControl extends StatePropsOfControlWithDetail {
    arraySchema: JsonSchema;
    childErrors?: ErrorObject[];
}
/**
 * Map state to table props
 *
 * @param state the store's state
 * @param ownProps any element's own props
 * @returns {StatePropsOfArrayControl} state props for a table control
 */
export declare const mapStateToArrayControlProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfArrayControl;
/**
 * Dispatch props of a table control
 */
export interface DispatchPropsOfArrayControl {
    addItem(path: string, value: any): () => void;
    removeItems?(path: string, toDelete: number[]): () => void;
    moveUp?(path: string, toMove: number): () => void;
    moveDown?(path: string, toMove: number): () => void;
}
/**
 * Maps state to dispatch properties of an array control.
 *
 * @param dispatch the store's dispatch method
 * @returns {DispatchPropsOfArrayControl} dispatch props of an array control
 */
export declare const mapDispatchToArrayControlProps: (dispatch: Dispatch<CoreActions>) => DispatchPropsOfArrayControl;
export interface DispatchPropsOfMultiEnumControl {
    addItem: (path: string, value: any) => void;
    removeItem?: (path: string, toDelete: any) => void;
}
export declare const mapDispatchToMultiEnumProps: (dispatch: Dispatch<CoreActions>) => DispatchPropsOfMultiEnumControl;
/**
 * Props of an array control.
 */
export interface ArrayControlProps extends StatePropsOfArrayControl, DispatchPropsOfArrayControl {
}
export declare const layoutDefaultProps: {
    visible: boolean;
    enabled: boolean;
    path: string;
    direction: 'row' | 'column';
};
/**
 * Map state to layout props.
 * @param state JSONForms state tree
 * @param ownProps any own props
 * @returns {StatePropsOfLayout}
 */
export declare const mapStateToLayoutProps: (state: JsonFormsState, ownProps: OwnPropsOfLayout) => LayoutProps;
export type RefResolver = (schema: JsonSchema) => Promise<JsonSchema>;
export interface OwnPropsOfJsonFormsRenderer extends OwnPropsOfRenderer {
}
export interface StatePropsOfJsonFormsRenderer extends OwnPropsOfJsonFormsRenderer {
    rootSchema: JsonSchema;
    config: any;
}
export interface JsonFormsProps extends StatePropsOfJsonFormsRenderer {
}
export declare const mapStateToJsonFormsRendererProps: (state: JsonFormsState, ownProps: OwnPropsOfJsonFormsRenderer) => StatePropsOfJsonFormsRenderer;
export declare const controlDefaultProps: {
    errors: string[];
    visible: boolean;
    enabled: boolean;
    path: string;
    direction: "row" | "column";
};
export interface StatePropsOfCombinator extends StatePropsOfControl {
    rootSchema: JsonSchema;
    path: string;
    id: string;
    indexOfFittingSchema: number;
    uischemas: JsonFormsUISchemaRegistryEntry[];
    data: any;
}
export declare const mapStateToCombinatorRendererProps: (state: JsonFormsState, ownProps: OwnPropsOfControl, keyword: CombinatorKeyword) => StatePropsOfCombinator;
export interface CombinatorRendererProps extends StatePropsOfCombinator, DispatchPropsOfControl {
}
/**
 * Map state to all of renderer props.
 * @param state the store's state
 * @param ownProps any own props
 * @returns {StatePropsOfCombinator} state props for a combinator
 */
export declare const mapStateToAllOfProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfCombinator;
export declare const mapStateToAnyOfProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfCombinator;
export declare const mapStateToOneOfProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfCombinator;
export interface StatePropsOfArrayLayout extends StatePropsOfControlWithDetail {
    data: number;
    arraySchema: JsonSchema;
    /**
     * @deprecated Use `arraySchema.minItems` instead.
     */
    minItems?: number;
    disableRemove?: boolean;
    disableAdd?: boolean;
}
/**
 * Map state to table props
 *
 * @param state the store's state
 * @param ownProps any element's own props
 * @returns {StatePropsOfArrayControl} state props for a table control
 */
export declare const mapStateToArrayLayoutProps: (state: JsonFormsState, ownProps: OwnPropsOfControl) => StatePropsOfArrayLayout;
/**
 * Props of an array control.
 */
export interface ArrayLayoutProps extends StatePropsOfArrayLayout, DispatchPropsOfArrayControl {
}
export interface StatePropsOfLabel extends StatePropsOfRenderer {
    text?: string;
}
export interface LabelProps extends StatePropsOfLabel {
}
export declare const mapStateToLabelProps: (state: JsonFormsState, props: OwnPropsOfLabel) => {
    text: string;
    visible: boolean;
    config: any;
    renderers: JsonFormsRendererRegistryEntry[];
    cells: JsonFormsCellRendererRegistryEntry[];
    uischema: LabelElement;
};
/**
 * Compute the child label title for array based controls
 * @param data the data of the control
 * @param childPath the child path
 * @param childLabelProp the dotted path to the value used as child label
 * @param {JsonSchema} schema the json schema for this control
 * @param {JsonSchema} rootSchema the root json schema
 * @param {Translator} translateFct the translator fonction
 * @param {UISchemaElement} uiSchema the uiSchema of the control
 */
export declare const computeChildLabel: (data: any, childPath: string, childLabelProp: string, schema: JsonSchema, rootSchema: JsonSchema, translateFct: Translator, uiSchema: UISchemaElement) => string;
