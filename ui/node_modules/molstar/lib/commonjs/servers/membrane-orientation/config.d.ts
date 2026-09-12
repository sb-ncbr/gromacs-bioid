/**
 * Copyright (c) 2024 mol* contributors, licensed under MIT, See LICENSE file for more info.
 *
 * @author Sebastian Bittrich <sebastian.bittrich@rcsb.org>
 */
declare const DefaultMembraneServerConfig: {
    /**
     * Node (V8) sometimes exhibits GC related issues  that significantly slow down the execution
     * (https://github.com/nodejs/node/issues/8670).
     *
     * Therefore an option is provided that automatically shuts down the server.
     * For this to work, the server must be run using a deamon (i.e. forever.js on Linux
     * or IISnode on Windows) so that the server is automatically restarted when the shutdown happens.
     */
    shutdownTimeoutMinutes: number;
    shutdownTimeoutVarianceMinutes: number;
    defaultPort: number;
    /**
     * Specify the prefix of the API, i.e.
     * <host>/<apiPrefix>/<API queries>
     */
    apiPrefix: string;
    /**
     * The maximum number of ms the server spends on a request
     */
    requestTimeoutMs: number;
    /**
     * Default URL from which BinaryCIF data will be pulled.
     */
    bcifSource: (id: string) => string;
};
export type MembraneServerConfig = typeof DefaultMembraneServerConfig;
export declare const MembraneServerConfig: {
    /**
     * Node (V8) sometimes exhibits GC related issues  that significantly slow down the execution
     * (https://github.com/nodejs/node/issues/8670).
     *
     * Therefore an option is provided that automatically shuts down the server.
     * For this to work, the server must be run using a deamon (i.e. forever.js on Linux
     * or IISnode on Windows) so that the server is automatically restarted when the shutdown happens.
     */
    shutdownTimeoutMinutes: number;
    shutdownTimeoutVarianceMinutes: number;
    defaultPort: number;
    /**
     * Specify the prefix of the API, i.e.
     * <host>/<apiPrefix>/<API queries>
     */
    apiPrefix: string;
    /**
     * The maximum number of ms the server spends on a request
     */
    requestTimeoutMs: number;
    /**
     * Default URL from which BinaryCIF data will be pulled.
     */
    bcifSource: (id: string) => string;
};
export declare function configureServer(): void;
export {};
