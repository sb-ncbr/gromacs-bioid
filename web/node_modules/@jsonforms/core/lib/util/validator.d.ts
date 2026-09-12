import Ajv from 'ajv';
import type { ErrorObject, Options, ValidateFunction } from 'ajv';
export declare const createAjv: (options?: Options) => Ajv;
export declare const validate: (validator: ValidateFunction | undefined, data: any) => ErrorObject[];
