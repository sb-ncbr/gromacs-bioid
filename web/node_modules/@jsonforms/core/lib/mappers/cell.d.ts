import { DispatchPropsOfControl, OwnPropsOfControl, OwnPropsOfEnum, StatePropsOfScopedRenderer } from './renderer';
import type { JsonSchema } from '../models';
import { AnyAction, Dispatch, JsonFormsCellRendererRegistryEntry, JsonFormsState } from '../store';
export interface OwnPropsOfCell extends OwnPropsOfControl {
    data?: any;
}
/**
 * State props of a cell.
 */
export interface StatePropsOfCell extends StatePropsOfScopedRenderer {
    isValid: boolean;
    rootSchema: JsonSchema;
}
export interface OwnPropsOfEnumCell extends OwnPropsOfCell, OwnPropsOfEnum {
}
/**
 * State props of a cell for enum cell
 */
export interface StatePropsOfEnumCell extends StatePropsOfCell, OwnPropsOfEnum {
}
/**
 * Props of an enum cell.
 */
export interface EnumCellProps extends StatePropsOfEnumCell, DispatchPropsOfControl {
}
export type DispatchPropsOfCell = DispatchPropsOfControl;
/**
 * Props of a cell.
 */
export interface CellProps extends StatePropsOfCell, DispatchPropsOfCell {
}
/**
 * Registers the given cell renderer when a JSON Forms store is created.
 * @param {RankedTester} tester
 * @param cell the cell to be registered
 * @returns {any}
 */
export interface DispatchCellStateProps extends StatePropsOfCell {
    cells?: JsonFormsCellRendererRegistryEntry[];
}
/**
 * Map state to cell props.
 *
 * @param state JSONForms state tree
 * @param ownProps any own props
 * @returns {StatePropsOfCell} state props of a cell
 */
export declare const mapStateToCellProps: (state: JsonFormsState, ownProps: OwnPropsOfCell) => StatePropsOfCell;
export declare const mapStateToDispatchCellProps: (state: JsonFormsState, ownProps: OwnPropsOfCell) => DispatchCellStateProps;
export interface DispatchCellProps extends DispatchCellStateProps {
}
/**
 * Default mapStateToCellProps for enum cell. Options is used for populating dropdown list
 * @param state
 * @param ownProps
 * @returns {StatePropsOfEnumCell}
 */
export declare const defaultMapStateToEnumCellProps: (state: JsonFormsState, ownProps: OwnPropsOfEnumCell) => StatePropsOfEnumCell;
/**
 * mapStateToOneOfEnumCellProps for one of enum cell. Options is used for populating dropdown list from oneOf
 * @param state
 * @param ownProps
 * @returns {StatePropsOfEnumCell}
 */
export declare const mapStateToOneOfEnumCellProps: (state: JsonFormsState, ownProps: OwnPropsOfEnumCell) => StatePropsOfEnumCell;
/**
 * Synonym for mapDispatchToControlProps.
 *
 * @type {(dispatch) => {handleChange(path, value): void}}
 */
export declare const mapDispatchToCellProps: (dispatch: Dispatch<AnyAction>) => DispatchPropsOfControl;
/**
 * Default dispatch to control props which can be customized to set handleChange action
 *
 */
export declare const defaultMapDispatchToControlProps: (dispatch: Dispatch<AnyAction>, ownProps: any) => DispatchPropsOfControl;
