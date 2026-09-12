import { ErrorObject } from 'ajv';
import { JsonSchema } from '../models';
export declare const getControlPath: (error: ErrorObject) => any;
export declare const errorsAt: (instancePath: string, schema: JsonSchema, matchPath: (path: string) => boolean) => (errors: ErrorObject[]) => ErrorObject[];
export declare const formatErrorMessage: (errors: string[]) => string;
