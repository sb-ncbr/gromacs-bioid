import { ControlElement, GroupLayout, Internationalizable, Labelable, Labeled, Layout, Scopable, Scoped, UISchemaElement } from '../models';
export type IterateCallback = (uischema: UISchemaElement) => void;
export declare const setReadonly: (uischema: UISchemaElement) => void;
export declare const unsetReadonly: (uischema: UISchemaElement) => void;
export declare const iterateSchema: (uischema: UISchemaElement, toApply: IterateCallback) => void;
/**
 * Find a control in a uiSchema, based on the dotted path of the schema value
 * @param {UISchemaElement} uiSchema the uiSchema to search from
 * @param path a dotted prop path to a schema value (i.e. articles.comment.author)
 * @return {UISchemaElement} or undefined if not found
 */
export declare const findUiControl: (uiSchema: UISchemaElement, path: string) => UISchemaElement | undefined;
export declare const composeWithUi: (scopableUi: Scopable, path: string) => string;
export declare const isInternationalized: (element: unknown) => element is Required<Internationalizable>;
export declare const isGroup: (layout: Layout) => layout is GroupLayout;
export declare const isLayout: (uischema: UISchemaElement) => uischema is Layout;
export declare const isScopable: (obj: unknown) => obj is Scopable;
export declare const isScoped: (obj: unknown) => obj is Scoped;
export declare const isLabelable: (obj: unknown) => obj is Labelable;
export declare const isLabeled: <T = never>(obj: unknown) => obj is Labeled<T>;
export declare const isControlElement: (uiSchema: UISchemaElement) => uiSchema is ControlElement;
